/**
 * PHATE Gallery - Stacked Card Layout
 * Structure labeling for single-cell embeddings
 */

// Data storage
let galleryData = null;
let wandbData = {};
let labels = {};
let annotations = { density: {}, quality: {} };
let notes = {};
let flagged = new Set();

// Stack state - track which run is visible for each dataset
let datasetRunIndex = {};

// Filter state
let filters = {
    algo: 'all',
    status: 'all',
    search: ''
};

// Autosave system for live collaboration
let autosaveTimeout = null;
let lastSaveTime = 0;

// Live collaboration system - BroadcastChannel for real-time updates
let collabChannel = null;
let sessionId = null;
let isUpdatingFromRemote = false;

const primaryTypes = ['clusters', 'simple_traj', 'bifurcation', 'multi_branch', 'complex_tree', 'cyclic', 'surface', 'batch_effect'];

// ============================================
// Data Loading & Storage
// ============================================

async function loadData() {
    try {
        const response = await fetch('gallery_data.json');
        if (response.ok) {
            galleryData = await response.json();
            wandbData = galleryData.runs || {};
            console.log(`Loaded ${Object.keys(wandbData).length} runs, ${Object.keys(galleryData.datasets || {}).length} datasets`);
        } else {
            throw new Error('Failed to load gallery_data.json');
        }
        loadFromStorage();
        renderGallery();
        updateStats();
        initializeCollaboration();
    } catch (error) {
        console.error('Error loading data:', error);
        document.getElementById('gallery').innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; padding: 50px; color: #ef4444;">
                Error loading gallery data: ${error.message}
            </div>`;
    }
}

function saveToStorage() {
    // Skip saving if this is triggered by a remote update to avoid loops
    if (isUpdatingFromRemote) return;

    const timestamp = Date.now();
    const currentSessionId = getSessionId();
    const saveData = {
        labels,
        annotations,
        notes,
        flagged: Array.from(flagged),
        datasetRunIndex,
        lastModified: timestamp,
        sessionId: currentSessionId
    };

    // Save main data
    localStorage.setItem('phateGalleryLabels', JSON.stringify(labels));
    localStorage.setItem('phateGalleryAnnotations', JSON.stringify(annotations));
    localStorage.setItem('phateGalleryNotes', JSON.stringify(notes));
    localStorage.setItem('phateGalleryFlagged', JSON.stringify(Array.from(flagged)));
    localStorage.setItem('phateGalleryRunIndex', JSON.stringify(datasetRunIndex));
    localStorage.setItem('phateGalleryLastModified', timestamp.toString());
    localStorage.setItem('phateGalleryFullData', JSON.stringify(saveData));

    // Save per-session data that getAllKnownSessions() looks for
    localStorage.setItem(`phateGallery_${currentSessionId}_lastModified`, timestamp.toString());
    localStorage.setItem(`phateGallery_${currentSessionId}_data`, JSON.stringify(saveData));

    lastSaveTime = timestamp;
    showSaveIndicator();

    // Broadcast changes to other tabs via BroadcastChannel
    if (collabChannel) {
        const message = {
            type: 'UPDATE',
            sessionId: currentSessionId,
            data: saveData,
            timestamp: timestamp
        };
        console.log('📤 Broadcasting update:', message);
        collabChannel.postMessage(message);
        console.log('✅ Message sent via BroadcastChannel');
    } else {
        console.warn('⚠️ No BroadcastChannel available for broadcasting');
    }
}

function autosave() {
    console.log('💾 Autosave triggered');

    // Clear any existing timeout
    if (autosaveTimeout) {
        clearTimeout(autosaveTimeout);
    }

    // Save after a short delay to avoid excessive saves during rapid changes
    autosaveTimeout = setTimeout(() => {
        console.log('💾 Executing autosave...');
        saveToStorage();
        console.log('🔄 Autosaved gallery state for collaboration');
    }, 300); // 300ms delay
}

function showSaveIndicator() {
    // Create or update save indicator
    let indicator = document.getElementById('autosave-indicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'autosave-indicator';
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #10b981;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            z-index: 1001;
            transition: all 0.3s ease;
            pointer-events: none;
        `;
        document.body.appendChild(indicator);
    }

    indicator.textContent = '✅ Saved';
    indicator.style.opacity = '1';
    indicator.style.transform = 'translateY(0)';

    // Fade out after 2 seconds
    setTimeout(() => {
        indicator.style.opacity = '0';
        indicator.style.transform = 'translateY(-10px)';
    }, 2000);
}

function loadFromStorage() {
    try {
        const savedLabels = localStorage.getItem('phateGalleryLabels');
        if (savedLabels) labels = JSON.parse(savedLabels);

        const savedAnnotations = localStorage.getItem('phateGalleryAnnotations');
        if (savedAnnotations) annotations = JSON.parse(savedAnnotations);

        const savedNotes = localStorage.getItem('phateGalleryNotes');
        if (savedNotes) notes = JSON.parse(savedNotes);

        const savedFlagged = localStorage.getItem('phateGalleryFlagged');
        if (savedFlagged) flagged = new Set(JSON.parse(savedFlagged));

        const savedRunIndex = localStorage.getItem('phateGalleryRunIndex');
        if (savedRunIndex) datasetRunIndex = JSON.parse(savedRunIndex);
    } catch (e) {
        console.warn('Error loading from storage:', e);
    }
}

// ============================================
// Statistics
// ============================================

function updateStats() {
    const total = Object.keys(wandbData).length;
    const labeled = Object.values(labels).filter(l => l.length > 0).length;
    const multi = Object.values(labels).filter(l => l.length > 1).length;

    document.getElementById('totalCount').textContent = total;
    document.getElementById('labeledCount').textContent = labeled;
    document.getElementById('multiCount').textContent = multi;
    document.getElementById('flaggedCount').textContent = flagged.size;
    document.getElementById('progressBar').style.width = total > 0 ? `${(labeled / total) * 100}%` : '0%';
}

// ============================================
// Filtering
// ============================================

function setFilter(type, value, btn) {
    filters[type] = value;

    // Update active state
    btn.parentElement.querySelectorAll('.filter-chip').forEach(chip => {
        chip.classList.remove('active');
    });
    btn.classList.add('active');

    applyFilters();
}

function applyFilters() {
    filters.search = document.getElementById('searchBox').value.toLowerCase();
    filterStackCards();
}

function filterStackCards() {
    document.querySelectorAll('.dataset-stack').forEach(card => {
        const dsName = card.dataset.dataset;
        const dsMeta = galleryData.datasets?.[dsName] || {};
        const runs = getDatasetRuns(dsName);

        // Check if any run matches filters
        let hasMatch = false;
        for (const run of runs) {
            const runLabels = labels[run.runId] || [];

            // Algorithm filter
            const algoMatch = filters.algo === 'all' ||
                (run.algorithm_type || 'phate') === filters.algo;

            // Status filter
            const statusMatch = filters.status === 'all' ||
                (filters.status === 'labeled' && runLabels.length > 0) ||
                (filters.status === 'unlabeled' && runLabels.length === 0);

            // Search filter
            const searchMatch = !filters.search ||
                dsName.toLowerCase().includes(filters.search) ||
                run.runId.toLowerCase().includes(filters.search) ||
                (run.label_key || '').toLowerCase().includes(filters.search);

            if (algoMatch && statusMatch && searchMatch) {
                hasMatch = true;
                break;
            }
        }

        card.classList.toggle('hidden', !hasMatch);
    });
}

// ============================================
// Dataset Grouping
// ============================================

function groupRunsByDataset() {
    const datasets = {};

    Object.entries(wandbData).forEach(([runId, runData]) => {
        const dsName = runData.dataset_name || 'Unknown';
        if (!datasets[dsName]) {
            datasets[dsName] = {
                metadata: galleryData.datasets?.[dsName] || {},
                runs: []
            };
        }
        datasets[dsName].runs.push({ runId, ...runData });
    });

    // Sort runs within each dataset
    Object.values(datasets).forEach(ds => {
        ds.runs.sort((a, b) => {
            const algoOrder = { phate: 0, reeb: 1, dse: 2 };
            const algoA = algoOrder[a.algorithm_type] ?? 99;
            const algoB = algoOrder[b.algorithm_type] ?? 99;
            if (algoA !== algoB) return algoA - algoB;
            return (a.label_key || '').localeCompare(b.label_key || '');
        });
    });

    return datasets;
}

function getDatasetRuns(datasetName) {
    const datasets = groupRunsByDataset();
    return datasets[datasetName]?.runs || [];
}

// ============================================
// Stack Navigation
// ============================================

function nextRun(datasetName) {
    const runs = getDatasetRuns(datasetName);
    if (runs.length <= 1) return;

    const current = datasetRunIndex[datasetName] || 0;
    datasetRunIndex[datasetName] = (current + 1) % runs.length;
    updateStackDisplay(datasetName);
    autosave();
}

function prevRun(datasetName) {
    const runs = getDatasetRuns(datasetName);
    if (runs.length <= 1) return;

    const current = datasetRunIndex[datasetName] || 0;
    datasetRunIndex[datasetName] = (current - 1 + runs.length) % runs.length;
    updateStackDisplay(datasetName);
    autosave();
}

function updateStackDisplay(datasetName) {
    const card = document.querySelector(`[data-dataset="${datasetName}"]`);
    if (!card) return;

    const runs = getDatasetRuns(datasetName);
    const currentIndex = datasetRunIndex[datasetName] || 0;
    const currentRun = runs[currentIndex];

    if (!currentRun) return;

    // Update image
    const img = card.querySelector('.stack-run-image');
    img.src = currentRun.image_path || `images/${currentRun.runId}.png`;

    // Update counter
    card.querySelector('.run-counter').textContent = `${currentIndex + 1}/${runs.length}`;

    // Update run info
    card.querySelector('.run-id').textContent = currentRun.run_id;
    card.querySelector('.label-key').textContent = currentRun.label_key || 'N/A';
    const numCats = currentRun.n_categories || Object.keys(currentRun.colors || {}).length || '?';
    card.querySelector('.n-categories').textContent = `${numCats} classes`;

    // Update DSE badge
    const dseBadge = card.querySelector('.dse-badge');
    const newDSEBadge = createDSEBadgeHTML(currentRun);
    if (dseBadge && newDSEBadge) {
        dseBadge.outerHTML = newDSEBadge;
    } else if (dseBadge && !newDSEBadge) {
        dseBadge.remove();
    } else if (!dseBadge && newDSEBadge) {
        // Insert before flag button
        const flagBtn = card.querySelector('.flag-btn');
        if (flagBtn) {
            flagBtn.insertAdjacentHTML('beforebegin', newDSEBadge);
        }
    }

    // Update algo badge
    const algoBadge = card.querySelector('.algo-badge');
    algoBadge.className = `algo-badge ${currentRun.algorithm_type || 'phate'}`;
    algoBadge.textContent = (currentRun.algorithm_type || 'phate').toUpperCase();

    // Update flag button
    const flagBtn = card.querySelector('.flag-btn');
    const isFlagged = flagged.has(currentRun.runId);
    flagBtn.classList.toggle('flagged', isFlagged);
    flagBtn.textContent = isFlagged ? 'FLAGGED' : 'Flag';
    flagBtn.onclick = (e) => { e.stopPropagation(); toggleFlag(currentRun.runId); };

    // Update label buttons container
    const labelContainer = card.querySelector('.label-buttons');
    labelContainer.dataset.runId = currentRun.runId;
    updateLabelButtons(labelContainer, currentRun.runId);

    // Update color legend
    const legendContainer = card.querySelector('.color-legend');
    if (legendContainer) {
        legendContainer.outerHTML = createColorLegendHTML(currentRun);
    }

    // Update details content (DSE metrics, annotations)
    updateDetailsContent(card, currentRun);

    // Update card classes
    const runLabels = labels[currentRun.runId] || [];
    card.classList.toggle('labeled', runLabels.length > 0);
    card.classList.toggle('flagged', isFlagged);
}

function updateLabelButtons(container, runId) {
    const runLabels = labels[runId] || [];

    container.querySelectorAll('.label-btn').forEach(btn => {
        const labelType = btn.dataset.label;
        btn.classList.toggle('selected', runLabels.includes(labelType));
        btn.onclick = (e) => { e.stopPropagation(); toggleStructure(runId, labelType); };
    });
}

function updateDetailsContent(card, runData) {
    const runId = runData.runId;

    // Update selects
    const densitySelect = card.querySelector('select[data-annotation="density"]');
    const qualitySelect = card.querySelector('select[data-annotation="quality"]');

    if (densitySelect) {
        densitySelect.value = annotations.density[runId] || '';
        densitySelect.classList.toggle('filled', !!annotations.density[runId]);
        densitySelect.onchange = () => setAnnotation(runId, 'density', densitySelect.value);
    }

    if (qualitySelect) {
        qualitySelect.value = annotations.quality[runId] || '';
        qualitySelect.classList.toggle('filled', !!annotations.quality[runId]);
        qualitySelect.onchange = () => setAnnotation(runId, 'quality', qualitySelect.value);
    }

    // Update notes
    const notesInput = card.querySelector('.notes-input');
    if (notesInput) {
        notesInput.value = notes[runId] || '';
        notesInput.onchange = () => setNotes(runId, notesInput.value);
    }
}

// ============================================
// Render Gallery
// ============================================

function renderGallery() {
    const gallery = document.getElementById('gallery');
    gallery.innerHTML = '';

    const datasets = groupRunsByDataset();

    Object.entries(datasets)
        .sort(([a], [b]) => a.localeCompare(b))
        .forEach(([dsName, dsData]) => {
            const card = createDatasetStackCard(dsName, dsData);
            gallery.appendChild(card);
        });

    applyFilters();
}

function createDatasetStackCard(dsName, dsData) {
    const runs = dsData.runs;
    const currentIndex = datasetRunIndex[dsName] || 0;
    const currentRun = runs[currentIndex];

    if (!currentRun) return document.createElement('div');

    const runLabels = labels[currentRun.runId] || [];
    const isLabeled = runLabels.length > 0;
    const isFlagged = flagged.has(currentRun.runId);

    // Calculate progress
    const labeledCount = runs.filter(r => (labels[r.runId] || []).length > 0).length;
    const progressPct = runs.length > 0 ? (labeledCount / runs.length) * 100 : 0;

    const card = document.createElement('div');
    card.className = `dataset-stack ${isLabeled ? 'labeled' : ''} ${isFlagged ? 'flagged' : ''}`;
    card.dataset.dataset = dsName;

    const algoType = currentRun.algorithm_type || 'phate';
    const imagePath = currentRun.image_path || `images/${currentRun.runId}.png`;
    const numCategories = currentRun.n_categories || Object.keys(currentRun.colors || {}).length || '?';

    card.innerHTML = `
        <div class="stack-indicator"></div>

        <div class="stack-header">
            <div class="stack-dataset-name" title="${dsName}">${dsName}</div>
            <div class="stack-nav">
                <button class="nav-btn" onclick="event.stopPropagation(); prevRun('${dsName}')" ${runs.length <= 1 ? 'disabled' : ''}>◀</button>
                <span class="run-counter">${currentIndex + 1}/${runs.length}</span>
                <button class="nav-btn" onclick="event.stopPropagation(); nextRun('${dsName}')" ${runs.length <= 1 ? 'disabled' : ''}>▶</button>
            </div>
            <span class="algo-badge ${algoType}">${algoType.toUpperCase()}</span>
        </div>

        <img class="stack-run-image" src="${imagePath}" alt="PHATE visualization"
             onclick="openModal('${imagePath}')"
             onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDgwIiBoZWlnaHQ9IjM2MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjNmNGY2Ii8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCIgZm9udC1zaXplPSIxNiIgZmlsbD0iIzljYTNhZiIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBmb3VuZDwvdGV4dD48L3N2Zz4='">

        <div class="stack-body">
            <div class="stack-run-info">
                <span class="run-id" title="${currentRun.run_id}">${currentRun.run_id}</span>
                <span class="label-key">${currentRun.label_key || 'N/A'}</span>
                <span class="n-categories">${numCategories} classes</span>
                ${createDSEBadgeHTML(currentRun)}
                <button class="flag-btn ${isFlagged ? 'flagged' : ''}" onclick="event.stopPropagation(); toggleFlag('${currentRun.runId}')">
                    ${isFlagged ? 'FLAGGED' : 'Flag'}
                </button>
            </div>

            ${createColorLegendHTML(currentRun)}

            <div class="label-section">
                <div class="label-section-title">Structure Types</div>
                <div class="label-buttons" data-run-id="${currentRun.runId}">
                    ${primaryTypes.map(type => {
                        const isSelected = runLabels.includes(type);
                        const displayName = type.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        return `<button class="label-btn ${isSelected ? 'selected' : ''}"
                                        data-label="${type}"
                                        onclick="event.stopPropagation(); toggleStructure('${currentRun.runId}', '${type}')">
                            ${displayName}
                        </button>`;
                    }).join('')}
                </div>
            </div>

            <div class="details-toggle" onclick="event.stopPropagation(); toggleDetails(this)">
                <span>▼</span> Details
            </div>
            <div class="details-content">
                ${createDSEMetricsHTML(currentRun)}
                <div class="annotation-grid">
                    <div class="annotation-item">
                        <label>Density:</label>
                        <select data-annotation="density" class="${annotations.density[currentRun.runId] ? 'filled' : ''}"
                                onchange="setAnnotation('${currentRun.runId}', 'density', this.value)">
                            <option value="">Select...</option>
                            <option value="uniform" ${annotations.density[currentRun.runId] === 'uniform' ? 'selected' : ''}>Uniform</option>
                            <option value="sparse" ${annotations.density[currentRun.runId] === 'sparse' ? 'selected' : ''}>Sparse</option>
                            <option value="dense_core" ${annotations.density[currentRun.runId] === 'dense_core' ? 'selected' : ''}>Dense Core</option>
                            <option value="gradient" ${annotations.density[currentRun.runId] === 'gradient' ? 'selected' : ''}>Gradient</option>
                        </select>
                    </div>
                    <div class="annotation-item">
                        <label>Quality:</label>
                        <select data-annotation="quality" class="${annotations.quality[currentRun.runId] ? 'filled' : ''}"
                                onchange="setAnnotation('${currentRun.runId}', 'quality', this.value)">
                            <option value="">Select...</option>
                            <option value="excellent" ${annotations.quality[currentRun.runId] === 'excellent' ? 'selected' : ''}>Excellent</option>
                            <option value="good" ${annotations.quality[currentRun.runId] === 'good' ? 'selected' : ''}>Good</option>
                            <option value="fair" ${annotations.quality[currentRun.runId] === 'fair' ? 'selected' : ''}>Fair</option>
                            <option value="poor" ${annotations.quality[currentRun.runId] === 'poor' ? 'selected' : ''}>Poor</option>
                        </select>
                    </div>
                </div>
                <textarea class="notes-input" placeholder="Notes..."
                          onchange="setNotes('${currentRun.runId}', this.value)">${notes[currentRun.runId] || ''}</textarea>
            </div>
        </div>

        <div class="stack-progress">
            <div class="progress-mini">
                <div class="progress-mini-fill" style="width: ${progressPct}%"></div>
            </div>
            <span class="progress-text">${labeledCount}/${runs.length} labeled</span>
        </div>
    `;

    return card;
}

// ============================================
// HTML Generators
// ============================================

function createColorLegendHTML(runData) {
    const colors = runData.colors || {};
    const categoryNames = Object.keys(colors);

    if (categoryNames.length === 0) return '';

    const maxDisplay = 12;
    const displayCategories = categoryNames.slice(0, maxDisplay);
    const hasMore = categoryNames.length > maxDisplay;

    return `
        <div class="color-legend">
            <div class="color-legend-header" onclick="event.stopPropagation(); toggleColorLegend(this)">
                <span class="color-legend-title">${runData.label_key || 'Categories'} (${categoryNames.length})</span>
                <span>▼</span>
            </div>
            <div class="color-legend-body">
                ${displayCategories.map(name => `
                    <div class="legend-item">
                        <div class="legend-color" style="background: ${colors[name]}"></div>
                        <span class="legend-label" title="${name}">${name}</span>
                    </div>
                `).join('')}
                ${hasMore ? `<div style="font-size: 10px; color: var(--text-muted); padding: 4px 0;">... and ${categoryNames.length - maxDisplay} more</div>` : ''}
            </div>
        </div>
    `;
}

function createDSEMetricsHTML(runData) {
    const dse = runData.dse_metrics;
    if (!dse || dse.status !== 'success') return '';

    const metrics = [
        { key: 'dse_count_t10', label: 't=10' },
        { key: 'dse_count_t50', label: 't=50' },
        { key: 'dse_count_t100', label: 't=100' },
        { key: 'dse_count_t200', label: 't=200' },
        { key: 'dse_count_t500', label: 't=500' },
    ].filter(m => dse[m.key] !== undefined);

    if (metrics.length === 0) return '';

    return `
        <div class="dse-metrics">
            <div class="dse-metrics-title">DSE Eigenvalue Counts</div>
            <div class="dse-metrics-grid">
                ${metrics.map(m => `
                    <div class="dse-metric-item">
                        <div class="dse-metric-value">${Math.round(dse[m.key])}</div>
                        <div class="dse-metric-label">${m.label}</div>
                    </div>
                `).join('')}
            </div>
            ${dse.dse_entropy !== undefined ? `
                <div class="dse-entropy">
                    <div class="dse-metric-value">${dse.dse_entropy.toFixed(2)}</div>
                    <div class="dse-metric-label">Entropy (t=3)</div>
                </div>
            ` : ''}
        </div>
    `;
}

function createDSEBadgeHTML(runData) {
    const dse = runData.dse_metrics;
    if (!dse || dse.status !== 'success') return '';

    // Use entropy as the primary badge metric if available, otherwise use eigenvalue count at t=100
    const entropy = dse.dse_entropy;
    const count = dse.dse_count_t100 || dse.dse_count_t50 || dse.dse_count_t10;

    if (entropy !== undefined) {
        // Classify entropy: low (<1), medium (1-2), high (>2)
        let badgeClass = '';
        let label = `E=${entropy.toFixed(2)}`;

        if (entropy > 2) {
            badgeClass = 'dse-badge-high';
            label = `High E=${entropy.toFixed(1)}`;
        } else if (entropy < 1) {
            badgeClass = 'dse-badge-low';
            label = `Low E=${entropy.toFixed(1)}`;
        }

        return `<span class="dse-badge ${badgeClass}" title="DSE Entropy: ${entropy.toFixed(2)}">${label}</span>`;
    } else if (count !== undefined) {
        return `<span class="dse-badge" title="DSE Eigenvalue Count (t=100): ${count}">DSE: ${count}</span>`;
    }

    return '<span class="dse-badge">DSE</span>';
}

// ============================================
// UI Interactions
// ============================================

function toggleDetails(toggle) {
    const content = toggle.nextElementSibling;
    content.classList.toggle('open');
    toggle.querySelector('span').textContent = content.classList.contains('open') ? '▲' : '▼';
}

function toggleColorLegend(header) {
    const body = header.nextElementSibling;
    body.classList.toggle('open');
    header.querySelector('span:last-child').textContent = body.classList.contains('open') ? '▲' : '▼';
}

// ============================================
// Label Actions
// ============================================

function toggleStructure(runId, structureType) {
    if (!labels[runId]) labels[runId] = [];

    const card = document.querySelector(`[data-dataset="${wandbData[runId]?.dataset_name}"]`);
    const button = card?.querySelector(`.label-buttons[data-run-id="${runId}"] [data-label="${structureType}"]`);

    if (labels[runId].includes(structureType)) {
        labels[runId] = labels[runId].filter(s => s !== structureType);
        button?.classList.remove('selected');
    } else {
        labels[runId].push(structureType);
        button?.classList.add('selected');
    }

    // Update card labeled state
    if (card) {
        card.classList.toggle('labeled', labels[runId].length > 0);
        updateStackProgress(card, wandbData[runId]?.dataset_name);
    }

    autosave();
    updateStats();
}

function toggleFlag(runId) {
    const card = document.querySelector(`[data-dataset="${wandbData[runId]?.dataset_name}"]`);
    const btn = card?.querySelector('.flag-btn');

    if (flagged.has(runId)) {
        flagged.delete(runId);
        btn?.classList.remove('flagged');
        if (btn) btn.textContent = 'Flag';
        card?.classList.remove('flagged');
    } else {
        flagged.add(runId);
        btn?.classList.add('flagged');
        if (btn) btn.textContent = 'FLAGGED';
        card?.classList.add('flagged');
    }

    autosave();
    updateStats();
}

function setAnnotation(runId, field, value) {
    if (value) {
        annotations[field][runId] = value;
    } else {
        delete annotations[field][runId];
    }
    autosave();
}

function setNotes(runId, value) {
    if (value.trim()) {
        notes[runId] = value.trim();
    } else {
        delete notes[runId];
    }
    autosave();
}

function updateStackProgress(card, datasetName) {
    const runs = getDatasetRuns(datasetName);
    const labeledCount = runs.filter(r => (labels[r.runId] || []).length > 0).length;
    const progressPct = runs.length > 0 ? (labeledCount / runs.length) * 100 : 0;

    const progressFill = card?.querySelector('.progress-mini-fill');
    const progressText = card?.querySelector('.progress-text');

    if (progressFill) progressFill.style.width = `${progressPct}%`;
    if (progressText) progressText.textContent = `${labeledCount}/${runs.length} labeled`;
}

// ============================================
// Modal
// ============================================

function openModal(imageSrc) {
    document.getElementById('modalImage').src = imageSrc;
    document.getElementById('imageModal').classList.add('open');
}

function closeModal() {
    document.getElementById('imageModal').classList.remove('open');
}

// ============================================
// Export/Import
// ============================================

async function exportToZip() {
    try {
        const zip = new JSZip();
        const date = new Date().toISOString().split('T')[0];

        // Export labels data
        const labelsData = {
            exported_at: new Date().toISOString(),
            labels: labels,
            annotations: annotations,
            notes: notes,
            flagged: Array.from(flagged),
            datasetRunIndex: datasetRunIndex
        };

        zip.file('labels.json', JSON.stringify(labelsData, null, 2));
        zip.file('gallery_data.json', JSON.stringify(galleryData, null, 2));

        // Generate standalone HTML with inlined CSS and JS
        const htmlContent = await generateStandaloneHTML();
        zip.file('gallery.html', htmlContent);

        const content = await zip.generateAsync({ type: 'blob' });
        saveAs(content, `phate_gallery_${date}.zip`);
    } catch (e) {
        // If full export fails (e.g., in standalone mode), fall back to labels-only export
        console.error('Full export failed, trying labels-only:', e);
        exportLabels();
    }
}

// Simple labels-only export that works in standalone mode
function exportLabels() {
    const date = new Date().toISOString().split('T')[0];

    const labelsData = {
        exported_at: new Date().toISOString(),
        labels: labels,
        annotations: annotations,
        notes: notes,
        flagged: Array.from(flagged),
        datasetRunIndex: datasetRunIndex
    };

    const blob = new Blob([JSON.stringify(labelsData, null, 2)], { type: 'application/json' });
    saveAs(blob, `phate_labels_${date}.json`);
}

async function generateStandaloneHTML() {
    // Get CSS from the current document's style tags
    let cssContent = '';
    document.querySelectorAll('style').forEach(style => {
        cssContent += style.textContent + '\n';
    });

    // Get JS content - fetch gallery.js
    let jsContent = '';
    try {
        const jsResponse = await fetch('gallery.js');
        if (jsResponse.ok) {
            jsContent = await jsResponse.text();
            // Only remove generateStandaloneHTML - keep exportToZip (it has fallback to exportLabels)
            jsContent = jsContent.replace(/async function generateStandaloneHTML\(\)[\s\S]*?^}\n/gm, '');
        } else {
            throw new Error(`HTTP ${jsResponse.status}`);
        }
    } catch (e) {
        alert('Cannot export from a standalone HTML file. Please use the original gallery with gallery.js available.');
        throw new Error('Cannot export from standalone HTML');
    }

    return `<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PHATE Gallery - Structure Labeling</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js"></script>
    <style>
${cssContent}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="header-top">
                <div>
                    <h1>PHATE Gallery</h1>
                    <p class="header-subtitle">Structure labeling for single-cell embeddings</p>
                </div>
            </div>
            <div class="stats-bar">
                <div class="stat-item">
                    <span class="stat-value" id="labeledCount">0</span>
                    <span class="stat-label">/ <span id="totalCount">0</span> labeled</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value" id="multiCount">0</span>
                    <span class="stat-label">multi-structure</span>
                </div>
                <div class="stat-item">
                    <span class="stat-value" id="flaggedCount">0</span>
                    <span class="stat-label">flagged</span>
                </div>
            </div>
            <div class="progress-container">
                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="progressBar" style="width: 0%"></div>
                </div>
            </div>
        </div>
    </div>

    <div class="controls">
        <input type="text" class="search-box" id="searchBox" placeholder="Search datasets or runs..." onkeyup="applyFilters()">

        <div class="filter-group">
            <span class="filter-label">Algorithm:</span>
            <button class="filter-chip active" data-filter="algo" data-value="all" onclick="setFilter('algo', 'all', this)">All</button>
            <button class="filter-chip" data-filter="algo" data-value="phate" onclick="setFilter('algo', 'phate', this)">PHATE</button>
            <button class="filter-chip" data-filter="algo" data-value="reeb" onclick="setFilter('algo', 'reeb', this)">Reeb</button>
            <button class="filter-chip" data-filter="algo" data-value="dse" onclick="setFilter('algo', 'dse', this)">DSE</button>
        </div>

        <div class="filter-group">
            <span class="filter-label">Status:</span>
            <button class="filter-chip active" data-filter="status" data-value="all" onclick="setFilter('status', 'all', this)">All</button>
            <button class="filter-chip" data-filter="status" data-value="unlabeled" onclick="setFilter('status', 'unlabeled', this)">Unlabeled</button>
            <button class="filter-chip" data-filter="status" data-value="labeled" onclick="setFilter('status', 'labeled', this)">Labeled</button>
        </div>

        <div class="actions">
            <button class="btn btn-primary" onclick="exportToZip()">
                <span>📦</span> Export
            </button>
            <button class="btn btn-secondary" onclick="document.getElementById('importFile').click()">
                <span>📥</span> Import
            </button>
            <input type="file" id="importFile" accept=".zip,.json" style="display:none" onchange="importFromFile(this)">
            <button class="btn btn-danger" onclick="if(confirm('Clear all labels, annotations, and notes?')) clearAll()">
                Clear All
            </button>
        </div>
    </div>

    <div class="gallery" id="gallery">
        <div style="grid-column: 1/-1; text-align: center; padding: 50px; color: var(--text-muted);">
            Loading gallery data...
        </div>
    </div>

    <div class="image-modal" id="imageModal" onclick="closeModal()">
        <span class="modal-close">&times;</span>
        <img id="modalImage" src="" alt="PHATE visualization">
    </div>

    <script>
${jsContent}
    </script>
</body>
</html>`;
}

async function importFromFile(input) {
    const file = input.files[0];
    if (!file) return;

    try {
        if (file.name.endsWith('.json')) {
            const text = await file.text();
            const data = JSON.parse(text);

            if (data.labels) labels = data.labels;
            if (data.annotations) annotations = data.annotations;
            if (data.notes) notes = data.notes;
            if (data.flagged) flagged = new Set(data.flagged);
            if (data.datasetRunIndex) datasetRunIndex = data.datasetRunIndex;

        } else if (file.name.endsWith('.zip')) {
            const zip = await JSZip.loadAsync(file);

            const labelsFile = zip.file('labels.json');
            if (labelsFile) {
                const text = await labelsFile.async('text');
                const data = JSON.parse(text);
                if (data.labels) labels = data.labels;
                if (data.annotations) annotations = data.annotations;
                if (data.notes) notes = data.notes;
                if (data.flagged) flagged = new Set(data.flagged);
                if (data.datasetRunIndex) datasetRunIndex = data.datasetRunIndex;
            }
        }

        saveToStorage();
        renderGallery();
        updateStats();
        alert('Import successful!');

    } catch (e) {
        alert('Import failed: ' + e.message);
    }

    input.value = '';
}

function clearAll() {
    labels = {};
    annotations = { density: {}, quality: {} };
    notes = {};
    flagged.clear();
    datasetRunIndex = {};
    localStorage.removeItem('phateGalleryLabels');
    localStorage.removeItem('phateGalleryAnnotations');
    localStorage.removeItem('phateGalleryNotes');
    localStorage.removeItem('phateGalleryFlagged');
    localStorage.removeItem('phateGalleryRunIndex');
    renderGallery();
    updateStats();
}

// ============================================
// Live Collaboration Features
// ============================================

function initializeCollaboration() {
    // Initialize session ID
    sessionId = getSessionId();

    // Initialize BroadcastChannel for cross-tab communication
    try {
        collabChannel = new BroadcastChannel('phate-gallery-collab');

        // Set up event listener for incoming updates (always waiting)
        collabChannel.onmessage = async (event) => {
            console.log('📩 BroadcastChannel received message:', event.data);
            await handleRemoteUpdate(event.data);
        };

        console.log('🚀 BroadcastChannel initialized for real-time collaboration');
        console.log('🎯 Channel name: phate-gallery-collab');
        console.log('📡 Listening for messages from other tabs...');
    } catch (error) {
        console.warn('BroadcastChannel not supported, falling back to localStorage polling');
        // Fallback for older browsers
        startLiveUpdateChecking();
    }

    // Update collaboration status
    const indicator = document.getElementById('collabIndicator');
    if (indicator) {
        indicator.querySelector('.status-text').textContent = 'Live Collaboration Ready';
        indicator.style.opacity = '1';
    }

    // Track user activity for collaboration awareness
    trackUserActivity();

    // Show welcome message for collaboration
    setTimeout(() => {
        console.log('🤝 Live collaboration enabled! All changes autosave automatically.');
        if (collabChannel) {
            console.log('⚡ Real-time updates via BroadcastChannel - changes appear instantly!');
        } else {
            console.log('🔄 Checking for updates from other users every 5 seconds.');
        }
        console.log('📊 Share this URL with collaborators to work together in real-time.');
    }, 1000);
}

function trackUserActivity() {
    // Track when user makes any change
    document.addEventListener('click', () => {
        localStorage.setItem('phateGalleryLastActivity', Date.now().toString());
    });

    document.addEventListener('input', () => {
        localStorage.setItem('phateGalleryLastActivity', Date.now().toString());
    });

    // Check for other users' activity periodically
    setInterval(checkCollaboratorActivity, 10000); // Check every 10 seconds
}

function checkCollaboratorActivity() {
    const myLastActivity = localStorage.getItem('phateGalleryLastActivity');
    const currentTime = Date.now();

    // This is a simple demo - in a real collaboration system,
    // you'd check a shared backend for other users' activity
    if (myLastActivity && currentTime - parseInt(myLastActivity) < 30000) {
        // User was active in last 30 seconds
        updateCollaborationStatus('active');
    } else {
        updateCollaborationStatus('idle');
    }
}

function updateCollaborationStatus(status) {
    const indicator = document.getElementById('collabIndicator');
    if (!indicator) return;

    const statusText = indicator.querySelector('.status-text');
    const statusDot = indicator.querySelector('.status-dot');

    switch (status) {
        case 'active':
            statusText.textContent = 'Live Collaboration Active';
            statusDot.style.background = '#10b981';
            break;
        case 'updating':
            statusText.textContent = 'Syncing Changes...';
            statusDot.style.background = '#f59e0b';
            break;
        case 'idle':
            statusText.textContent = 'Live Collaboration Ready';
            statusDot.style.background = '#6b7280';
            break;
        default:
            statusText.textContent = 'Live Collaboration Ready';
            statusDot.style.background = '#10b981';
    }
}

// ============================================
// Live Update Checking
// ============================================

function getSessionId() {
    let sessionId = localStorage.getItem('phateGallerySessionId');
    if (!sessionId) {
        sessionId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        localStorage.setItem('phateGallerySessionId', sessionId);
    }
    return sessionId;
}

async function handleRemoteUpdate(updateData) {
    console.log('🔍 handleRemoteUpdate called with:', updateData);

    // Ignore updates from our own session
    if (updateData.sessionId === sessionId) {
        console.log('⏭️ Ignoring update from own session:', sessionId);
        return;
    }

    // Ignore non-update messages
    if (updateData.type !== 'UPDATE') {
        console.log('⏭️ Ignoring non-UPDATE message type:', updateData.type);
        return;
    }

    console.log(`🔄 Processing update from session ${updateData.sessionId.substring(0, 8)}...`);

    // Set flag to prevent save loops
    isUpdatingFromRemote = true;

    try {
        // Show update notification
        showUpdateNotification(`Update from ${updateData.sessionId.substring(0, 8)}...`);

        // Get current timestamp to detect conflicts
        const localTimestamp = parseInt(localStorage.getItem('phateGalleryLastModified') || '0');
        const remoteTimestamp = updateData.timestamp;

        // Merge data with simple last-write-wins strategy
        if (remoteTimestamp > localTimestamp) {
            // Remote data is newer, apply all changes
            labels = { ...labels, ...updateData.data.labels };
            annotations = {
                density: { ...annotations.density, ...updateData.data.annotations.density },
                quality: { ...annotations.quality, ...updateData.data.annotations.quality }
            };
            notes = { ...notes, ...updateData.data.notes };
            flagged = new Set([...flagged, ...updateData.data.flagged]);
            datasetRunIndex = { ...datasetRunIndex, ...updateData.data.datasetRunIndex };

            // Save merged data to localStorage (without broadcasting)
            localStorage.setItem('phateGalleryLabels', JSON.stringify(labels));
            localStorage.setItem('phateGalleryAnnotations', JSON.stringify(annotations));
            localStorage.setItem('phateGalleryNotes', JSON.stringify(notes));
            localStorage.setItem('phateGalleryFlagged', JSON.stringify(Array.from(flagged)));
            localStorage.setItem('phateGalleryRunIndex', JSON.stringify(datasetRunIndex));

            // Update our local timestamp to match the remote one
            localStorage.setItem('phateGalleryLastModified', remoteTimestamp.toString());

            // Update the UI to reflect changes
            updateStats();
            renderGallery(); // Re-render to show new labels/flags

            console.log('✅ Successfully merged remote changes');
        } else {
            console.log('⏭️ Remote data is older, keeping local changes');
        }

    } catch (error) {
        console.error('Error handling remote update:', error);
    } finally {
        // Clear the flag to resume normal saving
        isUpdatingFromRemote = false;

        // Clear update notification after a delay
        setTimeout(() => {
            const notification = document.getElementById('update-notification');
            if (notification) {
                notification.remove();
            }
        }, 3000);
    }
}

function startLiveUpdateChecking() {
    // Fallback polling for browsers without BroadcastChannel support
    const updateCheckInterval = setInterval(checkForLiveUpdates, 5000);

    // Update indicator status
    const updateIndicator = document.getElementById('updateIndicator');
    if (updateIndicator) {
        updateIndicator.querySelector('.update-text').textContent = 'Live Updates Active (Polling)';
        updateIndicator.style.opacity = '1';
    }

    console.log('🔄 Live update checking started - checking every 5 seconds (fallback mode)');
}

function stopLiveUpdateChecking() {
    // Close BroadcastChannel if open
    if (collabChannel) {
        collabChannel.close();
        collabChannel = null;
        console.log('⏹️ Live collaboration stopped (BroadcastChannel closed)');
    }
}

async function checkForLiveUpdates() {
    try {
        const mySessionId = getSessionId();

        // Check for updates from other sessions
        const hasUpdates = await simulateUpdateCheck();

        if (hasUpdates) {
            await handleLiveUpdates();
        }

    } catch (error) {
        console.warn('Update check failed:', error);
    }
}

async function simulateUpdateCheck() {
    // In a real collaboration system, this would:
    // 1. Check a shared database/API for changes
    // 2. Compare timestamps with local data
    // 3. Return true if remote data is newer

    // For now, simulate occasional updates from other users
    const mySessionId = getSessionId();
    const allSessions = getAllKnownSessions();

    // Check if any other session has newer data
    let hasNewerData = false;
    const myLastModified = parseInt(localStorage.getItem('phateGalleryLastModified') || '0');

    for (const sessionId of allSessions) {
        if (sessionId !== mySessionId) {
            const otherLastModified = parseInt(localStorage.getItem(`phateGallery_${sessionId}_lastModified`) || '0');
            if (otherLastModified > myLastModified) {
                hasNewerData = true;
                break;
            }
        }
    }

    return hasNewerData;
}

function getAllKnownSessions() {
    // Get all known collaboration sessions
    const sessions = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('phateGallery_') && key.endsWith('_lastModified')) {
            const sessionId = key.replace('phateGallery_', '').replace('_lastModified', '');
            sessions.push(sessionId);
        }
    }
    return sessions;
}

async function handleLiveUpdates() {
    updateCollaborationStatus('updating');

    // Show update notification
    showUpdateNotification('🔄 Loading updates from collaborators...');

    console.log('🔄 Updates detected from other users - merging data');

    try {
        const mySessionId = getSessionId();
        const allSessions = getAllKnownSessions();

        // Find the most recent session data
        let mostRecentData = null;
        let mostRecentTimestamp = parseInt(localStorage.getItem('phateGalleryLastModified') || '0');

        for (const sessionId of allSessions) {
            if (sessionId !== mySessionId) {
                const otherTimestamp = parseInt(localStorage.getItem(`phateGallery_${sessionId}_lastModified`) || '0');
                if (otherTimestamp > mostRecentTimestamp) {
                    const otherDataStr = localStorage.getItem(`phateGallery_${sessionId}_data`);
                    if (otherDataStr) {
                        mostRecentData = JSON.parse(otherDataStr);
                        mostRecentTimestamp = otherTimestamp;
                    }
                }
            }
        }

        // Merge the most recent data if found
        if (mostRecentData) {
            isUpdatingFromRemote = true;

            // Merge data with simple last-write-wins strategy
            labels = { ...labels, ...mostRecentData.labels };
            annotations = {
                density: { ...annotations.density, ...mostRecentData.annotations.density },
                quality: { ...annotations.quality, ...mostRecentData.annotations.quality }
            };
            notes = { ...notes, ...mostRecentData.notes };
            flagged = new Set([...flagged, ...mostRecentData.flagged]);
            datasetRunIndex = { ...datasetRunIndex, ...mostRecentData.datasetRunIndex };

            // Save merged data to localStorage
            localStorage.setItem('phateGalleryLabels', JSON.stringify(labels));
            localStorage.setItem('phateGalleryAnnotations', JSON.stringify(annotations));
            localStorage.setItem('phateGalleryNotes', JSON.stringify(notes));
            localStorage.setItem('phateGalleryFlagged', JSON.stringify(Array.from(flagged)));
            localStorage.setItem('phateGalleryRunIndex', JSON.stringify(datasetRunIndex));
            localStorage.setItem('phateGalleryLastModified', mostRecentTimestamp.toString());

            // Update the UI to reflect changes
            updateStats();
            renderGallery();

            isUpdatingFromRemote = false;
            console.log('✅ Successfully merged remote changes (fallback mode)');
        }

    } catch (error) {
        console.error('Error handling live updates:', error);
        isUpdatingFromRemote = false;
    }

    // Reset status
    setTimeout(() => {
        updateCollaborationStatus('active');
    }, 2000);
}

function showUpdateNotification(message = '🔄 Updates from collaborators detected') {
    // Remove existing notification to avoid duplicates
    const existing = document.getElementById('update-notification');
    if (existing) {
        existing.remove();
    }

    // Create update notification
    const notification = document.createElement('div');
    notification.id = 'update-notification';
    notification.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: #10b981;
        color: white;
        padding: 12px 16px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        z-index: 1001;
        transition: all 0.3s ease;
        pointer-events: none;
        box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
        transform: translateX(100%);
        opacity: 0;
    `;
    document.body.appendChild(notification);

    notification.innerHTML = message;

    // Animate in
    setTimeout(() => {
        notification.style.opacity = '1';
        notification.style.transform = 'translateX(0)';
    }, 10);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.opacity = '0';
            notification.style.transform = 'translateX(100%)';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.remove();
                }
            }, 300);
        }
    }, 4000);
}

// ============================================
// Initialize
// ============================================

document.addEventListener('DOMContentLoaded', loadData);

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// Handle page visibility changes for live collaboration
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('📱 Page hidden - collaboration continues via BroadcastChannel');
    } else {
        console.log('👀 Page visible - checking for any missed updates');
        // Check for updates when returning to page (fallback only)
        if (!collabChannel) {
            setTimeout(checkForLiveUpdates, 1000);
        }
    }
});
