import { createContext, useContext, useReducer, useEffect } from 'react';

// Initial state matching the vanilla JS structure
const initialState = {
  galleryData: null,
  wandbData: {},
  labels: {},
  annotations: { density: {}, quality: {} },
  notes: {},
  flagged: new Set(),
  datasetRunIndex: {},
  filters: {
    algo: 'all',
    status: 'all',
    search: ''
  },
  sessionId: null,
  isLoading: true,
  isUpdatingFromRemote: false
};

// Primary structure types from original code
export const primaryTypes = [
  'clusters', 'simple_traj', 'bifurcation', 'multi_branch',
  'complex_tree', 'cyclic', 'surface', 'batch_effect'
];

// Action types
const actionTypes = {
  SET_GALLERY_DATA: 'SET_GALLERY_DATA',
  TOGGLE_LABEL: 'TOGGLE_LABEL',
  SET_ANNOTATION: 'SET_ANNOTATION',
  SET_NOTE: 'SET_NOTE',
  TOGGLE_FLAG: 'TOGGLE_FLAG',
  SET_FILTER: 'SET_FILTER',
  SET_SEARCH: 'SET_SEARCH',
  REMOTE_UPDATE: 'REMOTE_UPDATE',
  SET_LOADING: 'SET_LOADING',
  CLEAR_ALL: 'CLEAR_ALL',
  LOAD_FROM_STORAGE: 'LOAD_FROM_STORAGE'
};

// Reducer function
function appReducer(state, action) {
  switch (action.type) {
    case actionTypes.SET_GALLERY_DATA:
      return {
        ...state,
        galleryData: action.payload.galleryData,
        wandbData: action.payload.wandbData,
        datasetRunIndex: action.payload.datasetRunIndex,
        isLoading: false
      };

    case actionTypes.TOGGLE_LABEL: {
      const { runId, structureType } = action.payload;
      const currentLabels = state.labels[runId] || [];
      const newLabels = currentLabels.includes(structureType)
        ? currentLabels.filter(label => label !== structureType)
        : [...currentLabels, structureType];

      return {
        ...state,
        labels: {
          ...state.labels,
          [runId]: newLabels
        }
      };
    }

    case actionTypes.SET_ANNOTATION: {
      const { runId, annotationType, value } = action.payload;
      return {
        ...state,
        annotations: {
          ...state.annotations,
          [annotationType]: {
            ...state.annotations[annotationType],
            [runId]: value
          }
        }
      };
    }

    case actionTypes.SET_NOTE: {
      const { runId, note } = action.payload;
      const newNotes = { ...state.notes };
      if (note.trim() === '') {
        delete newNotes[runId];
      } else {
        newNotes[runId] = note;
      }
      return {
        ...state,
        notes: newNotes
      };
    }

    case actionTypes.TOGGLE_FLAG: {
      const { runId } = action.payload;
      const newFlagged = new Set(state.flagged);
      if (newFlagged.has(runId)) {
        newFlagged.delete(runId);
      } else {
        newFlagged.add(runId);
      }
      return {
        ...state,
        flagged: newFlagged
      };
    }

    case actionTypes.SET_FILTER: {
      const { filterType, value } = action.payload;
      return {
        ...state,
        filters: {
          ...state.filters,
          [filterType]: value
        }
      };
    }

    case actionTypes.SET_SEARCH:
      return {
        ...state,
        filters: {
          ...state.filters,
          search: action.payload
        }
      };

    case actionTypes.REMOTE_UPDATE: {
      const { labels, annotations, notes, flagged } = action.payload;
      return {
        ...state,
        labels: labels || state.labels,
        annotations: annotations || state.annotations,
        notes: notes || state.notes,
        flagged: new Set(flagged || state.flagged),
        isUpdatingFromRemote: true
      };
    }

    case actionTypes.SET_LOADING:
      return {
        ...state,
        isLoading: action.payload
      };

    case actionTypes.CLEAR_ALL:
      return {
        ...state,
        labels: {},
        annotations: { density: {}, quality: {} },
        notes: {},
        flagged: new Set()
      };

    case actionTypes.LOAD_FROM_STORAGE:
      return {
        ...state,
        labels: action.payload.labels || {},
        annotations: action.payload.annotations || { density: {}, quality: {} },
        notes: action.payload.notes || {},
        flagged: new Set(action.payload.flagged || []),
        datasetRunIndex: action.payload.datasetRunIndex || {}
      };

    default:
      return state;
  }
}

// Helper to generate session ID
function generateSessionId() {
  return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
}

const AppContext = createContext();

export const AppProvider = ({ children }) => {
  const [state, dispatch] = useReducer(appReducer, {
    ...initialState,
    sessionId: generateSessionId()
  });

  // Load data from localStorage on mount
  useEffect(() => {
    const loadFromStorage = () => {
      try {
        const savedLabels = localStorage.getItem('phateGalleryLabels');
        const savedAnnotations = localStorage.getItem('phateGalleryAnnotations');
        const savedNotes = localStorage.getItem('phateGalleryNotes');
        const savedFlagged = localStorage.getItem('phateGalleryFlagged');
        const savedRunIndex = localStorage.getItem('phateGalleryRunIndex');

        dispatch({
          type: actionTypes.LOAD_FROM_STORAGE,
          payload: {
            labels: savedLabels ? JSON.parse(savedLabels) : {},
            annotations: savedAnnotations ? JSON.parse(savedAnnotations) : { density: {}, quality: {} },
            notes: savedNotes ? JSON.parse(savedNotes) : {},
            flagged: savedFlagged ? JSON.parse(savedFlagged) : [],
            datasetRunIndex: savedRunIndex ? JSON.parse(savedRunIndex) : {}
          }
        });
      } catch (error) {
        console.error('Error loading from localStorage:', error);
      }
    };

    loadFromStorage();
  }, []);

  // Auto-save to localStorage when state changes
  useEffect(() => {
    if (!state.isLoading && !state.isUpdatingFromRemote) {
      try {
        localStorage.setItem('phateGalleryLabels', JSON.stringify(state.labels));
        localStorage.setItem('phateGalleryAnnotations', JSON.stringify(state.annotations));
        localStorage.setItem('phateGalleryNotes', JSON.stringify(state.notes));
        localStorage.setItem('phateGalleryFlagged', JSON.stringify([...state.flagged]));
        localStorage.setItem('phateGalleryRunIndex', JSON.stringify(state.datasetRunIndex));

        // Save per-session data for collaboration
        const timestamp = Date.now();
        const sessionData = {
          labels: state.labels,
          annotations: state.annotations,
          notes: state.notes,
          flagged: [...state.flagged],
          timestamp
        };
        localStorage.setItem(`phateGallery_${state.sessionId}`, JSON.stringify(sessionData));
      } catch (error) {
        console.error('Error saving to localStorage:', error);
      }
    }

    // Reset remote update flag after processing
    if (state.isUpdatingFromRemote) {
      setTimeout(() => {
        dispatch({ type: actionTypes.SET_LOADING, payload: false });
      }, 100);
    }
  }, [state.labels, state.annotations, state.notes, state.flagged, state.datasetRunIndex, state.isLoading, state.isUpdatingFromRemote, state.sessionId]);

  const value = {
    state,
    dispatch,
    actionTypes
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within AppProvider');
  }
  return context;
};
