#!/usr/bin/env python3
"""
Generic config generator for ManyLatents experiments.

This module generates experiment configuration files for any algorithm,
not just PHATE. It creates the YAML configs needed by ManyLatents.
"""

import h5py
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field


@dataclass
class ConfigPaths:
    """Paths for config generation."""
    data_dir: Path
    output_base: Path
    experiment_dir: Path
    manylatents_dir: Path


@dataclass
class AlgorithmParams:
    """Parameters for an algorithm."""
    n_components: int = 2
    knn: int = 100
    t: int = 12
    decay: int = 60
    # Additional params can be passed via extra_params
    extra_params: Dict[str, Any] = field(default_factory=dict)


def clean_name(filename: str) -> str:
    """Convert filename to a clean experiment name."""
    name = filename.replace('.h5ad', '').replace(' ', '_').replace('-', '_')
    # Remove special characters
    name = ''.join(c for c in name if c.isalnum() or c == '_')
    return name


# Priority columns for auto-detecting label_key
#
# Recommended priority order:
# 1. Condition (diseased, healthy)
# 2. Stages/perturbations (developmental stages, disease progression, treatments)
# 3. Cell Type
# 4. Longitudinal Times (Day, timepoint)
#
# TIER_1: Condition - disease vs healthy, treatment status
TIER_1_CONDITION = [
    'disease', 'Disease', 'disease_status',
    'condition', 'Condition',
    'health_status', 'health', 'Health',
    'status', 'Status',
    'disease_state', 'disease_type',
    'cv19_vax_boost_or_HC_status', 'infection_status', 'vaccination_status',
    'COVID_status', 'covid_status',
    'patient_status', 'subject_status',
]

# TIER_2: Stages and Perturbations - developmental stages, disease progression, treatments
TIER_2_STAGES = [
    # Developmental stages
    'development_stage', 'developmental_stage', 'stage', 'Stage',
    'Carnegie_stage', 'carnegie_stage',
    'gestational_week', 'gestational_age', 'GA',
    'trimester', 'Trimester',
    # Disease progression
    'BraakStage', 'braak_stage', 'Braak_stage',
    'disease_stage', 'tumor_stage', 'cancer_stage',
    'pathologic_stage', 'pathology_stage',
    # Perturbations/treatments
    'treatment', 'Treatment', 'perturbation', 'stimulus',
    'drug', 'Drug', 'compound',
    'intervention', 'Intervention',
    'patient_group', 'PatientGroup', 'patient_type',
    'group', 'Group', 'cohort', 'Cohort',
    # Lineage/differentiation (trajectory-related)
    'lineage', 'Lineage', 'pseudotime', 'dpt_pseudotime',
    'dpt', 'diffusion_pseudotime',
]

# TIER_3: Cell Type - identity of cells
TIER_3_CELLTYPE = [
    'cell_type',
    'author_cell_type', 'AuthorCellType',
    'celltype', 'CellType', 'cell_type_original',
    'major_celltype', 'broad_cell_type',
    'cell_type_broad', 'celltype_broad',
    'cell_type_fine', 'celltype_fine',
    'annotated_celltype', 'annotated_cell_type',
    'consensus_cell_type', 'consensus_celltype',
]

# TIER_4: Longitudinal Time - time points, longitudinal measurements
TIER_4_TEMPORAL = [
    'Day', 'day', 'days',
    'timepoint', 'time_point', 'TimePoint', 'time',
    'DayFactor', 'day_factor',
    'time_point_days', 'days_post_infection', 'dpi',
    'age', 'Age', 'age_days', 'age_weeks',
    'visit', 'Visit', 'timepoint_visit',
    'longitudinal_time', 'visit_number',
]

# TIER_5: Clustering/annotation - fallback if nothing else found
TIER_5_CLUSTER = [
    'cluster', 'Cluster', 'clusters',
    'leiden', 'louvain', 'seurat_clusters',
    'annotation', 'Annotation', 'cell_annotation',
    'cell_annotation_label', 'cluster_label',
    'celltype.final', 'celltype.broad_clustering_annot',
    'major_labl', 'region', 'Region', 'zone', 'Zone',
    'location', 'Location',
]


def auto_detect_label_key(
    h5ad_path: Path,
    min_categories: int = 2,
    max_categories: int = 100,
) -> Optional[str]:
    """
    Auto-detect the best label column for visualization.

    Args:
        h5ad_path: Path to H5AD file
        min_categories: Minimum categories to be useful
        max_categories: Maximum categories before too noisy

    Returns:
        Column name or None if not found
    """
    if not h5ad_path.exists():
        return None

    try:
        with h5py.File(h5ad_path, 'r') as f:
            obs = f['obs']
            available_cols = set(obs.keys())

            # Check each tier in priority order
            # 1. Condition, 2. Stages, 3. Cell Type, 4. Time, 5. Clusters
            for tier_cols in [TIER_1_CONDITION, TIER_2_STAGES, TIER_3_CELLTYPE, TIER_4_TEMPORAL, TIER_5_CLUSTER]:
                for col in tier_cols:
                    if col in available_cols:
                        col_data = obs[col]
                        # Check if categorical and get category count
                        if 'categories' in col_data:
                            n_cats = len(col_data['categories'][:])
                            if min_categories <= n_cats <= max_categories:
                                return col
                        # Also check string columns with reasonable unique values
                        elif col_data.dtype.kind in ['U', 'O', 'S']:
                            # For string columns, estimate unique count from first 1000 values
                            try:
                                sample = col_data[:1000]
                                unique_vals = set(str(v) for v in sample if v)
                                if min_categories <= len(unique_vals) <= max_categories:
                                    return col
                            except Exception:
                                pass

            # Fallback to cell_type if exists
            if 'cell_type' in available_cols:
                return 'cell_type'

    except Exception as e:
        print(f"Warning: Could not auto-detect label for {h5ad_path.name}: {e}")

    return None


class AlgorithmConfigGenerator:
    """Generate ManyLatents configs for any algorithm."""

    def __init__(
        self,
        algorithm_name: str,
        manylatents_dir: Path,
        data_dir: Path,
        output_base: Path,
        project_name: Optional[str] = None,
    ):
        """
        Initialize the config generator.

        Args:
            algorithm_name: Name of algorithm (e.g., "phate", "umap", "tsne")
            manylatents_dir: Path to ManyLatents installation
            data_dir: Directory containing H5AD files
            output_base: Base directory for experiment outputs
            project_name: Optional project name (defaults to {algorithm}_cellxgene)
        """
        self.algorithm = algorithm_name.lower()
        self.manylatents_dir = Path(manylatents_dir)
        self.data_dir = Path(data_dir)
        self.output_base = Path(output_base)
        self.experiment_dir = self.manylatents_dir / "configs" / "experiment" / "cellxgene"
        self.project_name = project_name or f"{self.algorithm}_cellxgene"
        self.paths = ConfigPaths(
            data_dir=self.data_dir,
            output_base=self.output_base,
            experiment_dir=self.experiment_dir,
            manylatents_dir=self.manylatents_dir,
        )

    def create_experiment_config(
        self,
        h5ad_path: Path,
        algorithm_params: Optional[Dict[str, Any]] = None,
        auto_detect_label: bool = True,
    ) -> tuple[Dict[str, Any], str]:
        """
        Create an experiment config for a single dataset.

        Args:
            h5ad_path: Path to H5AD file
            algorithm_params: Optional algorithm-specific parameters
            auto_detect_label: Whether to auto-detect label_key from h5ad file

        Returns:
            Tuple of (config dict, experiment name)
        """
        filename = h5ad_path.name
        exp_name = clean_name(filename)
        dataset_id = filename.replace('.h5ad', '')

        # Default params
        if algorithm_params is None:
            algorithm_params = {"n_components": 2}

        # Auto-detect label_key
        label_key = None
        if auto_detect_label:
            label_key = auto_detect_label_key(h5ad_path)

        config = {
            "name": f"{self.algorithm}_{exp_name}",
            "seed": 42,
            "project": self.project_name,
            "data": {
                "adata_path": str(h5ad_path),
                "label_key": label_key,
            },
            "algorithms": {
                "latent": algorithm_params
            }
        }

        return config, exp_name

    def write_config_file(
        self,
        config: Dict[str, Any],
        exp_name: str,
    ) -> Path:
        """
        Write a config file to disk.

        Args:
            config: Configuration dictionary
            exp_name: Experiment name

        Returns:
            Path to written config file
        """
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        config_path = self.experiment_dir / f"{exp_name}.yaml"

        with open(config_path, 'w') as f:
            # Write the @package directive as a comment
            f.write("# @package _global_\n")
            # Write name
            f.write(f"name: {config['name']}\n\n")
            # Write defaults
            f.write("defaults:\n")
            f.write(f"  - override /algorithms/latent: {self.algorithm}\n")
            f.write("  - override /data: cellxgene_dataset\n")
            f.write("  - override /callbacks/embedding: default\n")
            f.write("  - override /metrics: test_metric\n\n")
            # Write the rest
            f.write(f"seed: {config['seed']}\n")
            f.write(f"project: {config['project']}\n\n")
            # Write data section
            f.write("data:\n")
            f.write(f"  adata_path: {config['data']['adata_path']}\n")
            f.write(f"  label_key: {config['data']['label_key']}\n\n")
            # Write algorithms section
            f.write("algorithms:\n")
            f.write("  latent:\n")
            for key, value in config['algorithms']['latent'].items():
                f.write(f"    {key}: {value}\n")

        return config_path

    def generate_configs(
        self,
        algorithm_params: Optional[Dict[str, Any]] = None,
        pattern: str = "*.h5ad",
        auto_detect_label: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Generate experiment configs for all H5AD files.

        Args:
            algorithm_params: Algorithm-specific parameters
            pattern: Glob pattern for matching files
            auto_detect_label: Whether to auto-detect label_key from h5ad files

        Returns:
            List of config dictionaries with metadata
        """
        # Create directories
        self.experiment_dir.mkdir(parents=True, exist_ok=True)
        self.output_base.mkdir(parents=True, exist_ok=True)

        # Find all H5AD files
        h5ad_files = list(self.data_dir.glob(pattern))
        print(f"Data directory: {self.data_dir}")
        print(f"Found {len(h5ad_files)} H5AD files")

        if not h5ad_files:
            print("Warning: No H5AD files found!")
            return []

        # Generate experiment configs
        config_list = []
        for h5ad_path in sorted(h5ad_files):
            config, exp_name = self.create_experiment_config(
                h5ad_path, algorithm_params, auto_detect_label
            )

            # Write config file
            config_path = self.write_config_file(config, exp_name)

            entry = {
                "name": exp_name,
                "h5ad_file": h5ad_path.name,
                "config_path": str(config_path),
                "algorithm": self.algorithm,
            }

            # Add label_key info if detected
            if config["data"]["label_key"]:
                entry["label_key"] = config["data"]["label_key"]
                print(f"Created config: {exp_name} (label_key: {config['data']['label_key']})")
            else:
                print(f"Created config: {exp_name} (no label_key detected)")

            config_list.append(entry)

        # Create master list file
        master_list_path = self.manylatents_dir / f"{self.algorithm}_experiments.yaml"
        with open(master_list_path, 'w') as f:
            yaml.dump({"experiments": config_list}, f, default_flow_style=False)

        print(f"\nCreated {len(config_list)} experiment configs")
        print(f"Master list saved to: {master_list_path}")
        print(f"Outputs will be saved to: {self.output_base}")

        return config_list

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "AlgorithmConfigGenerator":
        """Create generator from configuration dictionary."""
        return cls(
            algorithm_name=config["algorithm_name"],
            manylatents_dir=Path(config["manylatents_dir"]),
            data_dir=Path(config["data_dir"]),
            output_base=Path(config.get("output_base", "")),
            project_name=config.get("project_name"),
        )


def main():
    """CLI entry point for config generation."""
    import argparse

    DEFAULT_DATA_DIR = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/subsampled")
    DEFAULT_MANYLATENTS_DIR = Path("/home/btd8/manylatents")
    DEFAULT_OUTPUT_BASE = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs")

    parser = argparse.ArgumentParser(
        description="Generate ManyLatents experiment configs for any algorithm"
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        default="phate",
        help="Algorithm name (default: phate)"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(DEFAULT_DATA_DIR),
        help=f"Directory with H5AD files (default: {DEFAULT_DATA_DIR})"
    )
    parser.add_argument(
        "--manylatents-dir",
        type=str,
        default=str(DEFAULT_MANYLATENTS_DIR),
        help=f"Path to ManyLatents installation (default: {DEFAULT_MANYLATENTS_DIR})"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(DEFAULT_OUTPUT_BASE),
        help=f"Base output directory (default: {DEFAULT_OUTPUT_BASE})"
    )
    parser.add_argument(
        "--n-components",
        type=int,
        default=2,
        help="Number of components (default: 2)"
    )
    parser.add_argument(
        "--knn",
        type=int,
        default=100,
        help="Number of nearest neighbors (default: 100)"
    )
    parser.add_argument(
        "--t",
        type=int,
        default=12,
        help="PHATE diffusion time (default: 12)"
    )
    parser.add_argument(
        "--decay",
        type=int,
        default=60,
        help="PHATE decay (default: 60)"
    )
    parser.add_argument(
        "--no-auto-detect",
        action="store_true",
        help="Disable auto-detection of label_key (will use None)"
    )

    args = parser.parse_args()

    # Build algorithm params based on algorithm type
    algorithm_params = {"n_components": args.n_components}
    if args.algorithm.lower() == "phate":
        algorithm_params.update({"knn": args.knn, "t": args.t, "decay": args.decay})

    # Create generator and generate configs
    generator = AlgorithmConfigGenerator(
        algorithm_name=args.algorithm,
        manylatents_dir=args.manylatents_dir,
        data_dir=args.data_dir,
        output_base=args.output_dir,
    )

    generator.generate_configs(
        algorithm_params=algorithm_params,
        auto_detect_label=not args.no_auto_detect
    )


if __name__ == "__main__":
    main()
