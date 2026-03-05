import { useState } from 'react';
import { useAppContext } from '../context/AppContext';
import LabelButtons from './LabelButtons';

const DatasetCard = ({ dataset, runs }) => {
  const { state, dispatch, actionTypes } = useAppContext();
  const [currentRunIndex, setCurrentRunIndex] = useState(0);

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
    // Simple modal implementation - could be improved with proper modal context
    const modal = document.getElementById('imageModal');
    const modalImage = document.getElementById('modalImage');
    if (modal && modalImage) {
      modalImage.src = runData.image_path;
      modal.classList.add('open');
    }
  };

  // Algorithm badge
  const getAlgoBadge = () => {
    
    if (runData.algorithm_type) {
      const algo = runData.algorithm_type.toLowerCase();
      return (
        <span className={`algo-badge ${algo}`}>
          {algo}
        </span>
      );
    }
    return null;
  };

  // Progress calculation for this dataset
  const labeledRunsInDataset = runs.filter(runId => {
    const labels = state.labels[runId] || [];
    return labels.length > 0;
  }).length;
  const progressPercent = Math.round((labeledRunsInDataset / runs.length) * 100);

  return (
    <div className={`dataset-stack ${isLabeled ? 'labeled' : ''} ${isFlagged ? 'flagged' : ''}`}>
      {runs.length > 1 && <div className="stack-indicator"></div>}

      <div className="stack-header">
        <div className="stack-dataset-name" title={dataset}>
          {dataset}
        </div>
        {runs.length > 1 && (
          <div className="stack-nav">
            <button
              className="nav-btn"
              onClick={goToPrevRun}
              disabled={currentRunIndex === 0}
            >
              ←
            </button>
            <span className="run-counter">
              {currentRunIndex + 1}/{runs.length}
            </span>
            <button
              className="nav-btn"
              onClick={goToNextRun}
              disabled={currentRunIndex === runs.length - 1}
            >
              →
            </button>
          </div>
        )}
      </div>

      <img
        src={runData.image_path}
        alt={`PHATE visualization for ${dataset}`}
        className="stack-run-image"
        onClick={openModal}
      />

      <div className="stack-body">
        <div className="stack-run-info">
          <span className="run-id" title={currentRun}>
            {currentRun}
          </span>
          {getAlgoBadge()}
          <button
            className={`flag-btn ${isFlagged ? 'flagged' : ''}`}
            onClick={toggleFlag}
          >
            🏴 {isFlagged ? 'Flagged' : 'Flag'}
          </button>
        </div>

        <LabelButtons runId={currentRun} />

        {/* Annotation Grid */}
        <div className="annotation-grid">
          <div className="annotation-item">
            <label>Density</label>
            <select
              value={state.annotations.density[currentRun] || ''}
              onChange={(e) => setAnnotation('density', e.target.value)}
              className={state.annotations.density[currentRun] ? 'filled' : ''}
            >
              <option value="">-</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div className="annotation-item">
            <label>Quality</label>
            <select
              value={state.annotations.quality[currentRun] || ''}
              onChange={(e) => setAnnotation('quality', e.target.value)}
              className={state.annotations.quality[currentRun] ? 'filled' : ''}
            >
              <option value="">-</option>
              <option value="poor">Poor</option>
              <option value="good">Good</option>
              <option value="excellent">Excellent</option>
            </select>
          </div>
        </div>

        {/* Notes */}
        <textarea
          className="notes-input"
          placeholder="Add notes..."
          value={state.notes[currentRun] || ''}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>

      {/* Progress for multi-run datasets */}
      {runs.length > 1 && (
        <div className="stack-progress">
          <div className="progress-mini">
            <div
              className="progress-mini-fill"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>
          <div className="progress-text">
            {labeledRunsInDataset}/{runs.length} labeled
          </div>
        </div>
      )}
    </div>
  );
};

export default DatasetCard;
