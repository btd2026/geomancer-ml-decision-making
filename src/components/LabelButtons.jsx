import { useAppContext, primaryTypes } from '../context/AppContext';

const LabelButtons = ({ runId }) => {
  const { state, dispatch, actionTypes } = useAppContext();

  const runLabels = state.labels[runId] || [];

  const handleToggle = (structureType) => {
    dispatch({
      type: actionTypes.TOGGLE_LABEL,
      payload: { runId, structureType }
    });
  };

  return (
    <div className="label-section">
      <div className="label-section-title">Structure Types</div>
      <div className="label-buttons">
        {primaryTypes.map(type => {
          const isSelected = runLabels.includes(type);
          const displayName = type.replace(/_/g, ' ');

          return (
            <button
              key={type}
              className={`label-btn ${isSelected ? 'selected' : ''}`}
              data-label={type}
              onClick={() => handleToggle(type)}
            >
              {displayName}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default LabelButtons;
