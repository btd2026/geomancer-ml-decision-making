import { useMemo } from 'react';
import { useAppContext } from '../context/AppContext';
import DatasetCard from './DatasetCard';

const Gallery = () => {
  const { state } = useAppContext();

  // Filter and organize runs by dataset
  const filteredDatasets = useMemo(() => {
    if (!state.galleryData || !state.datasetRunIndex) {
      return {};
    }

    const { algo, status, search } = state.filters;

    const filteredIndex = {};

    Object.entries(state.datasetRunIndex).forEach(([dataset, runs]) => {
      const filteredRuns = runs.filter(runId => {
        const runData = state.wandbData[runId];
        if (!runData) return false;

        // Algorithm filter
        if (algo !== 'all') {
          const runAlgo = runData.algorithm_type?.toLowerCase();
          if (runAlgo !== algo) return false;
        }

        // Status filter
        if (status !== 'all') {
          const isLabeled = (state.labels[runId] || []).length > 0;
          if (status === 'labeled' && !isLabeled) return false;
          if (status === 'unlabeled' && isLabeled) return false;
        }

        // Search filter
        if (search) {
          const searchTerm = search.toLowerCase();
          const datasetMatch = dataset.toLowerCase().includes(searchTerm);
          const runIdMatch = runId.toLowerCase().includes(searchTerm);
          if (!datasetMatch && !runIdMatch) return false;
        }

        return true;
      });

      if (filteredRuns.length > 0) {
        filteredIndex[dataset] = filteredRuns;
      }
    });

    return filteredIndex;
  }, [state.galleryData, state.datasetRunIndex, state.wandbData, state.filters, state.labels]);

  const datasetEntries = Object.entries(filteredDatasets);

  if (state.isLoading) {
    return (
      <div className="gallery">
        <div style={{
          gridColumn: '1/-1',
          textAlign: 'center',
          padding: '50px',
          color: 'var(--text-muted)'
        }}>
          Loading gallery data...
        </div>
      </div>
    );
  }

  if (datasetEntries.length === 0) {
    return (
      <div className="gallery">
        <div style={{
          gridColumn: '1/-1',
          textAlign: 'center',
          padding: '50px',
          color: 'var(--text-muted)'
        }}>
          No datasets match the current filters.
        </div>
      </div>
    );
  }

  return (
    <div className="gallery">
      {datasetEntries.map(([dataset, runs]) => (
        <DatasetCard
          key={dataset}
          dataset={dataset}
          runs={runs}
        />
      ))}
    </div>
  );
};

export default Gallery;
