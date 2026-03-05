import { useRef } from 'react';
import { useAppContext } from '../context/AppContext';

const Controls = () => {
  const { state, dispatch, actionTypes } = useAppContext();
  const fileInputRef = useRef();

  const handleSearch = (e) => {
    dispatch({
      type: actionTypes.SET_SEARCH,
      payload: e.target.value
    });
  };

  const setFilter = (filterType, value) => {
    dispatch({
      type: actionTypes.SET_FILTER,
      payload: { filterType, value }
    });
  };

  const exportToZip = async () => {
    try {
      const JSZip = window.JSZip;
      if (!JSZip) {
        alert('JSZip library not loaded. Please refresh the page.');
        return;
      }

      const zip = new JSZip();

      // Export data
      const exportData = {
        labels: state.labels,
        annotations: state.annotations,
        notes: state.notes,
        flagged: [...state.flagged],
        exportedAt: new Date().toISOString(),
        version: '2.0'
      };

      zip.file('phate_gallery_data.json', JSON.stringify(exportData, null, 2));

      const content = await zip.generateAsync({ type: 'blob' });
      const url = URL.createObjectURL(content);
      const a = document.createElement('a');
      a.href = url;
      a.download = `phate_gallery_export_${new Date().toISOString().split('T')[0]}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Export failed:', error);
      alert('Export failed. Please try again.');
    }
  };

  const importFromFile = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    try {
      const text = await file.text();
      let data;

      if (file.name.endsWith('.json')) {
        data = JSON.parse(text);
      } else if (file.name.endsWith('.zip')) {
        const JSZip = window.JSZip;
        if (!JSZip) {
          alert('JSZip library not loaded. Please refresh the page.');
          return;
        }

        const zip = await JSZip.loadAsync(file);
        const jsonFile = zip.file('phate_gallery_data.json');
        if (!jsonFile) {
          alert('Invalid ZIP file. Missing phate_gallery_data.json');
          return;
        }
        const jsonText = await jsonFile.async('string');
        data = JSON.parse(jsonText);
      } else {
        alert('Invalid file format. Please use JSON or ZIP files.');
        return;
      }

      // Validate and import data
      const importPayload = {
        labels: data.labels || {},
        annotations: data.annotations || { density: {}, quality: {} },
        notes: data.notes || {},
        flagged: data.flagged || []
      };

      dispatch({
        type: actionTypes.LOAD_FROM_STORAGE,
        payload: importPayload
      });

      alert(`Successfully imported ${Object.keys(importPayload.labels).length} labels`);
    } catch (error) {
      console.error('Import failed:', error);
      alert('Import failed. Please check the file format.');
    }

    // Reset file input
    e.target.value = '';
  };

  const clearAll = () => {
    if (confirm('Clear all labels, annotations, and notes? This cannot be undone.')) {
      dispatch({ type: actionTypes.CLEAR_ALL });
    }
  };

  return (
    <div className="controls">
      <input
        type="text"
        className="search-box"
        placeholder="Search datasets or runs..."
        value={state.filters.search}
        onChange={handleSearch}
      />

      <div className="filter-group">
        <span className="filter-label">Algorithm:</span>
        {['all', 'phate', 'reeb', 'dse'].map(algo => (
          <button
            key={algo}
            className={`filter-chip ${state.filters.algo === algo ? 'active' : ''}`}
            onClick={() => setFilter('algo', algo)}
          >
            {algo.charAt(0).toUpperCase() + algo.slice(1)}
          </button>
        ))}
      </div>

      <div className="filter-group">
        <span className="filter-label">Status:</span>
        {['all', 'unlabeled', 'labeled'].map(status => (
          <button
            key={status}
            className={`filter-chip ${state.filters.status === status ? 'active' : ''}`}
            onClick={() => setFilter('status', status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </button>
        ))}
      </div>

      <div className="actions">
        <button className="btn btn-primary" onClick={exportToZip}>
          <span>📦</span> Export ZIP
        </button>
        <button
          className="btn btn-secondary"
          onClick={() => fileInputRef.current?.click()}
        >
          <span>📥</span> Import
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".zip,.json"
          style={{ display: 'none' }}
          onChange={importFromFile}
        />
        <button className="btn btn-danger" onClick={clearAll}>
          Clear All
        </button>
      </div>
    </div>
  );
};

export default Controls;
