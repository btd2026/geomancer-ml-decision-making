import { useEffect } from 'react';
import { AppProvider, useAppContext } from './context/AppContext';
import Gallery from './components/Gallery';
import Header from './components/Header';
import Controls from './components/Controls';
import ImageModal from './components/ImageModal';
import { useCollaboration } from './hooks/useCollaboration';
import './App.css';

// Inner app component that uses context
const AppContent = () => {
  const { state, dispatch, actionTypes } = useAppContext();
  const collaboration = useCollaboration();

  // Load gallery data on mount
  useEffect(() => {
    const loadGalleryData = async () => {
      try {
        const response = await fetch('/geomancer-ml-decision-making/gallery_data.json');
        const data = await response.json();

        // Build dataset run index
        const datasetRunIndex = {};
        Object.keys(data).forEach(runId => {
          const dataset = data[runId].dataset;
          if (!datasetRunIndex[dataset]) {
            datasetRunIndex[dataset] = [];
          }
          datasetRunIndex[dataset].push(runId);
        });

        dispatch({
          type: actionTypes.SET_GALLERY_DATA,
          payload: {
            galleryData: data,
            wandbData: data,
            datasetRunIndex
          }
        });

        console.log('Gallery data loaded:', Object.keys(data).length, 'runs');
      } catch (error) {
        console.error('Error loading gallery data:', error);
        dispatch({ type: actionTypes.SET_LOADING, payload: false });
      }
    };

    loadGalleryData();
  }, [dispatch, actionTypes]);

  if (state.isLoading) {
    return (
      <div style={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        height: '100vh',
        fontSize: '18px',
        color: 'var(--text-muted, #666)'
      }}>
        Loading gallery data...
      </div>
    );
  }

  return (
    <>
      <Header />
      <Controls />
      <Gallery />
      <ImageModal />
    </>
  );
};

// Main app component with provider
const App = () => {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
};

export default App;
