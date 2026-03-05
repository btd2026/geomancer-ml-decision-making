import { useState } from 'react';
import { useAppContext } from '../context/AppContext';
import LabelButtons from './LabelButtons';
import './ModernCard.css';

const ModernDatasetCard = ({ dataset, runs }) => {
  const { state, dispatch, actionTypes } = useAppContext();
  const [currentRunIndex, setCurrentRunIndex] = useState(0);
  const [showLegend, setShowLegend] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  const currentRun = runs[currentRunIndex];
  const runData = state.wandbData[currentRun];

  if (!runData) return null;

  const runLabels = state.labels[currentRun] || [];
  const isLabeled = runLabels.length > 0;
  const isFlagged = state.flagged.has(currentRun);

  const goToPrevRun = () => {
    setCurrentRunIndex(prev => Math.max(0, prev - 1));
  };

  const goToNextRun = () => {
    setCurrentRunIndex(prev => Math.min(runs.length - 1, prev + 1));
  };

  const toggleFlag = () => {
    dispatch({
      type: actionTypes.TOGGLE_FLAG,
      payload: { runId: currentRun }
    });
  };

  const setAnnotation = (annotationType, value) => {
    dispatch({
      type: actionTypes.SET_ANNOTATION,
      payload: { runId: currentRun, annotationType, value }
    });
  };

  const setNote = (note) => {
    dispatch({
      type: actionTypes.SET_NOTE,
      payload: { runId: currentRun, note }
    });
  };

  const openModal = () => {
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    if (modal && modalImage) {
      modalImage.src = runData.image_path;
      modal.classList.add('open');
    }
  };

  // Format large numbers
  const formatNumber = (num) => {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num?.toLocaleString() || 'N/A';
  };

  // Progress calculation
  const labeledRunsInDataset = runs.filter(runId => {
    const labels = state.labels[runId] || [];
    return labels.length > 0;
  }).length;
  const progressPercent = Math.round((labeledRunsInDataset / runs.length) * 100);

  // DSE metrics
  const dseMetrics = runData.dse_metrics || {};
  const dseEntropy = dseMetrics.dse_entropy?.toFixed(2) || 'N/A';

  // Color legend data
  const colors = runData.colors || {};
  const categories = runData.categories || [];

  return (
    <div className={`modern-dataset-card ${isLabeled ? 'labeled' : ''} ${isFlagged ? 'flagged' : ''}`}>

      {/* Header with dataset info and navigation */}
      <div className="card-header">
        <div className="dataset-info">
          <h3 className="dataset-name" title={dataset}>
            {dataset.replace(/_/g, ' ').substring(0, 40)}
            {dataset.length > 40 && '...'}
          </h3>
          <div className="metadata-pills">
            <span className={`algo-pill ${runData.algorithm_type}`}>
              {runData.algorithm_type?.toUpperCase()}
            </span>
            <span className="size-pill">
              {formatNumber(runData.n_obs)} cells
            </span>
            <span className="categories-pill">
              {runData.n_categories} types
            </span>
          </div>
        </div>

        {runs.length > 1 && (
          <div className="navigation">
            <button className="nav-button" onClick={goToPrevRun} disabled={currentRunIndex === 0}>
              ‹
            </button>
            <span className="nav-counter">{currentRunIndex + 1}/{runs.length}</span>
            <button className="nav-button" onClick={goToNextRun} disabled={currentRunIndex === runs.length - 1}>
              ›
            </button>
          </div>
        )}
      </div>

      {/* Main visualization */}
      <div className="visualization-container" onClick={openModal}>
        <img
          src={runData.image_path}
          alt={`PHATE visualization for ${dataset}`}
          className="visualization-image"
        />
        <div className="image-overlay">
          <span className="zoom-hint">🔍 Click to enlarge</span>
        </div>
      </div>

      {/* DSE Metrics Bar */}
      {dseMetrics.dse_entropy && (
        <div className="dse-metrics-bar">
          <div className="dse-header">
            <span className="dse-title">DSE Entropy</span>
            <span className="dse-value">{dseEntropy}</span>
          </div>
          <div className="dse-details">
            <div className="dse-mini-metrics">
              <span>t10: {dseMetrics.dse_count_t10?.toFixed(0) || 'N/A'}</span>
              <span>t50: {dseMetrics.dse_count_t50?.toFixed(0) || 'N/A'}</span>
              <span>t100: {dseMetrics.dse_count_t100?.toFixed(0) || 'N/A'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Color Legend */}
      <div className="legend-section">
        <button
          className="legend-toggle"
          onClick={() => setShowLegend(!showLegend)}
        >
          <span>Color Legend ({categories.length} categories)</span>
          <span className={`toggle-icon ${showLegend ? 'open' : ''}`}>▼</span>
        </button>
        {showLegend && (
          <div className="legend-content">
            {categories.slice(0, 12).map((category, index) => (
              <div key={category} className="legend-item">
                <div
                  className="legend-color"
                  style={{ backgroundColor: colors[category] || '#999' }}
                ></div>
                <span className="legend-label" title={category}>
                  {category.length > 20 ? category.substring(0, 20) + '...' : category}
                </span>
              </div>
            ))}
            {categories.length > 12 && (
              <div className="legend-item">
                <span className="legend-more">+{categories.length - 12} more...</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Labeling Interface */}
      <div className="labeling-section">
        <LabelButtons runId={currentRun} />

        <div className="annotations-row">
          <select
            value={state.annotations.density[currentRun] || ''}
            onChange={(e) => setAnnotation('density', e.target.value)}
            className="annotation-select"
          >
            <option value="">Density?</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>

          <select
            value={state.annotations.quality[currentRun] || ''}
            onChange={(e) => setAnnotation('quality', e.target.value)}
            className="annotation-select"
          >
            <option value="">Quality?</option>
            <option value="poor">Poor</option>
            <option value="good">Good</option>
            <option value="excellent">Excellent</option>
          </select>
        </div>
      </div>

      {/* Footer with actions */}
      <div className="card-footer">
        <button
          className={`flag-button ${isFlagged ? 'flagged' : ''}`}
          onClick={toggleFlag}
        >
          {isFlagged ? '🏴 Flagged' : '🏳️ Flag for Review'}
        </button>

        <button
          className="details-button"
          onClick={() => setShowDetails(!showDetails)}
        >
          {showDetails ? 'Hide Details' : 'Show Details'}
        </button>
      </div>

      {/* Expandable Details */}
      {showDetails && (
        <div className="details-section">
          <div className="detail-grid">
            <div className="detail-item">
              <label>Run ID:</label>
              <span className="detail-value" title={currentRun}>
                {currentRun.substring(0, 20)}...
              </span>
            </div>
            <div className="detail-item">
              <label>Features:</label>
              <span className="detail-value">{formatNumber(runData.n_vars)}</span>
            </div>
            <div className="detail-item">
              <label>Label Key:</label>
              <span className="detail-value">{runData.label_key || 'N/A'}</span>
            </div>
          </div>

          <textarea
            className="notes-input"
            placeholder="Add research notes..."
            value={state.notes[currentRun] || ''}
            onChange={(e) => setNote(e.target.value)}
          />
        </div>
      )}

      {/* Progress indicator for multi-run datasets */}
      {runs.length > 1 && (
        <div className="progress-indicator">
          <div className="progress-track">
            <div
              className="progress-fill"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
          <span className="progress-text">
            {labeledRunsInDataset}/{runs.length} labeled ({progressPercent}%)
          </span>
        </div>
      )}
    </div>
  );
};

export default ModernDatasetCard;
