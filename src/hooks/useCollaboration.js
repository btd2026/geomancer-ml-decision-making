import { useEffect, useRef } from 'react';
import { useAppContext } from '../context/AppContext';

export const useCollaboration = () => {
  const { state, dispatch, actionTypes } = useAppContext();
  const channelRef = useRef(null);
  const lastUpdateRef = useRef(0);

  useEffect(() => {
    // Initialize BroadcastChannel for cross-tab collaboration
    if ('BroadcastChannel' in window) {
      channelRef.current = new BroadcastChannel('phate-gallery-collab');

      channelRef.current.onmessage = async (event) => {
        const { type, sessionId, data, timestamp } = event.data;

        // Ignore messages from same session
        if (sessionId === state.sessionId) {
          return;
        }

        // Prevent processing the same update multiple times
        if (timestamp <= lastUpdateRef.current) {
          return;
        }

        lastUpdateRef.current = timestamp;

        console.log(`[Collab] Received ${type} from session ${sessionId}:`, data);

        if (type === 'UPDATE') {
          await handleRemoteUpdate(data, sessionId, timestamp);
        }
      };

      console.log('[Collab] BroadcastChannel initialized');
    } else {
      console.warn('[Collab] BroadcastChannel not supported, falling back to localStorage polling');
      // Fallback to localStorage polling for older browsers
      startStoragePolling();
    }

    return () => {
      if (channelRef.current) {
        channelRef.current.close();
      }
    };
  }, [state.sessionId]);

  // Handle remote updates from other tabs/users
  const handleRemoteUpdate = async (remoteData, remoteSessionId, timestamp) => {
    try {
      // Merge remote data with current data (last-write-wins strategy)
      const mergedData = {
        labels: { ...state.labels, ...remoteData.labels },
        annotations: {
          density: { ...state.annotations.density, ...(remoteData.annotations?.density || {}) },
          quality: { ...state.annotations.quality, ...(remoteData.annotations?.quality || {}) }
        },
        notes: { ...state.notes, ...remoteData.notes },
        flagged: [...new Set([...state.flagged, ...(remoteData.flagged || [])])]
      };

      // Update React state
      dispatch({
        type: actionTypes.REMOTE_UPDATE,
        payload: mergedData
      });

      // Show notification
      showUpdateNotification(remoteSessionId);

      console.log('[Collab] Remote update applied:', mergedData);
    } catch (error) {
      console.error('[Collab] Error handling remote update:', error);
    }
  };

  // Broadcast updates to other tabs when state changes
  useEffect(() => {
    if (!state.isLoading && !state.isUpdatingFromRemote && channelRef.current) {
      const timestamp = Date.now();

      // Only broadcast if enough time has passed since last update to avoid spam
      if (timestamp - lastUpdateRef.current > 1000) {
        const updateData = {
          type: 'UPDATE',
          sessionId: state.sessionId,
          data: {
            labels: state.labels,
            annotations: state.annotations,
            notes: state.notes,
            flagged: [...state.flagged]
          },
          timestamp
        };

        channelRef.current.postMessage(updateData);

        console.log(`[Collab] Broadcasting update from session ${state.sessionId}:`, updateData.data);
      }
    }
  }, [state.labels, state.annotations, state.notes, state.flagged, state.isLoading, state.isUpdatingFromRemote, state.sessionId]);

  // Fallback storage polling for older browsers
  const startStoragePolling = () => {
    setInterval(() => {
      checkForStorageUpdates();
    }, 5000); // Check every 5 seconds
  };

  const checkForStorageUpdates = () => {
    try {
      const knownSessions = getAllKnownSessions();

      for (const sessionId of knownSessions) {
        if (sessionId === state.sessionId) continue;

        const sessionData = localStorage.getItem(`phateGallery_${sessionId}`);
        if (sessionData) {
          const data = JSON.parse(sessionData);
          if (data.timestamp > lastUpdateRef.current) {
            handleRemoteUpdate(data, sessionId, data.timestamp);
            break; // Process one update at a time
          }
        }
      }
    } catch (error) {
      console.error('[Collab] Error checking storage updates:', error);
    }
  };

  const getAllKnownSessions = () => {
    const sessions = new Set();
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith('phateGallery_session_')) {
        const sessionId = key.replace('phateGallery_', '');
        sessions.add(sessionId);
      }
    }
    return Array.from(sessions);
  };

  const showUpdateNotification = (remoteSessionId) => {
    // Create a temporary notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
      position: fixed;
      top: 70px;
      right: 20px;
      background: #4CAF50;
      color: white;
      padding: 12px 20px;
      border-radius: 8px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      z-index: 10000;
      font-family: -apple-system, BlinkMacSystemFont, sans-serif;
      font-size: 14px;
      animation: slideIn 0.3s ease-out;
    `;
    notification.textContent = `Updates received from ${remoteSessionId.substring(0, 12)}...`;

    // Add animation
    const style = document.createElement('style');
    style.textContent = `
      @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
    `;
    document.head.appendChild(style);

    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
      notification.style.animation = 'slideOut 0.3s ease-in forwards';
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
        if (style.parentNode) {
          style.parentNode.removeChild(style);
        }
      }, 300);
    }, 3000);

    // Add slideOut animation
    style.textContent += `
      @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
      }
    `;
  };

  return {
    isCollaborationEnabled: !!channelRef.current,
    sessionId: state.sessionId
  };
};
