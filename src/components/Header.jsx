import { useAppContext } from '../context/AppContext';
import { useCollaboration } from '../hooks/useCollaboration';

const Header = () => {
  const { state } = useAppContext();
  const { isCollaborationEnabled, sessionId } = useCollaboration();

  // Calculate stats
  const total = Object.keys(state.wandbData).length;
  const labeled = Object.values(state.labels).filter(l => l.length > 0).length;
  const multi = Object.values(state.labels).filter(l => l.length > 1).length;
  const flagged = state.flagged.size;

  const progressPercentage = total > 0 ? Math.round((labeled / total) * 100) : 0;

  return (
    <div className="header">
      <div className="header-content">
        <div className="header-top">
          <div>
            <h1>PHATE Gallery</h1>
            <p className="header-subtitle">Structure labeling for single-cell embeddings</p>
          </div>
          <div className="collab-status">
            <div className="collab-indicator">
              <span className="status-dot"></span>
              <span className="status-text">
                {isCollaborationEnabled ? 'Live Collaboration Ready' : 'Collaboration Unavailable'}
              </span>
            </div>
            <div className="update-indicator">
              <span className="update-dot"></span>
              <span className="update-text">Live Updates</span>
            </div>
          </div>
        </div>

        <div className="stats-bar">
          <div className="stat-item">
            <span className="stat-value">{labeled}</span>
            <span className="stat-label">/ {total} labeled</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{multi}</span>
            <span className="stat-label">multi-structure</span>
          </div>
          <div className="stat-item">
            <span className="stat-value">{flagged}</span>
            <span className="stat-label">flagged</span>
          </div>
        </div>

        <div className="progress-container">
          <div className="progress-bar-bg">
            <div
              className="progress-bar-fill"
              style={{ width: `${progressPercentage}%` }}
            ></div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Header;
