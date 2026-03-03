"""
Generate ManyLatents experiment configs from user config.

This script reads the phate_experiments.yaml config and generates
corresponding ManyLatents experiment YAML files.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Default ManyLatents experiment config directory
DEFAULT_MANYLATENTS_EXPERIMENT_DIR = Path(
    "/home/btd8/manylatents/manylatents/configs/experiment"
)


def load_user_config(config_path: str | Path) -> dict[str, Any]:
    """Load the user experiments config YAML."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_slurm_resources(
    config: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    """Get SLURM resources from preset or experiment override."""
    preset_name = experiment.get("slurm_preset", config.get("defaults", {}).get("slurm_preset", "medium"))

    presets = config.get("slurm_presets", {})
    if preset_name in presets:
        return presets[preset_name]

    # Default medium preset
    return {
        "mem_gb": 32,
        "cpus_per_task": 4,
        "timeout_min": 240,
        "partition": "day",
    }


def get_phate_params(
    config: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    """Get PHATE parameters from defaults and experiment override."""
    defaults = config.get("defaults", {}).get("phate", {})
    override = experiment.get("phate", {})

    return {**defaults, **override}


def get_label_key(config: dict[str, Any], experiment: dict[str, Any]) -> str:
    """Get label key from config, experiment, or default to 'auto'."""
    if "label_key" in experiment:
        return experiment["label_key"]
    return config.get("defaults", {}).get("label_key", "auto")


def get_full_h5ad_path(config: dict[str, Any], experiment: dict[str, Any]) -> str:
    """Construct full H5AD path from base dir and experiment file."""
    base_dir = config.get("h5ad_base_dir", "")
    h5ad_file = experiment.get("h5ad_file", experiment.get("name") + ".h5ad")

    if Path(h5ad_file).is_absolute():
        return h5ad_file

    return str(Path(base_dir) / h5ad_file)


def generate_experiment_config(
    config: dict[str, Any],
    experiment: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    """
    Generate a ManyLatents experiment config for a single experiment.

    Args:
        config: The full user config dict.
        experiment: A single experiment dict.
        output_dir: Directory to save the generated config.

    Returns:
        Tuple of (config_path, metadata_dict).
    """
    name = experiment["name"]
    phate_params = get_phate_params(config, experiment)
    label_key = get_label_key(config, experiment)
    h5ad_path = get_full_h5ad_path(config, experiment)
    resources = get_slurm_resources(config, experiment)
    output_options = config.get("defaults", {}).get("output", {})

    # Build ManyLatents config structure
    ml_config = {
        "name": f"phate_{name}",
        "seed": phate_params.get("seed", 42),
        "project": config.get("project", "geomancer-phate"),
    }

    # Defaults section for ManyLatents
    ml_config["defaults"] = [
        "override /algorithms/latent: phate",
        "override /data: anndata",
        "override /callbacks/embedding: default",
        "override /logger: none",  # Use none to avoid wandb issues
    ]

    # Algorithm parameters
    ml_config["algorithms"] = {
        "latent": {
            "n_components": phate_params.get("n_components", 2),
            "knn": phate_params.get("knn", 100),
            "t": phate_params.get("t", 12),
            "decay": phate_params.get("decay", 60),
        }
    }

    # Data configuration
    ml_config["data"] = {
        "adata_path": h5ad_path,
        "test_split": 0.0,
        "_metadata_": {
            "label_key": label_key,
            "extract_metadata": output_options.get("extract_metadata", True),
        },
    }

    # Output directory override
    if config.get("output_dir"):
        ml_config["callbacks"] = {
            "embedding": {
                "output_dir": str(Path(config["output_dir"]) / name),
            }
        }

    # Store metadata for manifest (resources are for manifest only, not written to config)
    metadata = {
        "name": name,
        "h5ad_path": h5ad_path,
        "label_key": label_key,
        "phate_params": phate_params,
        "resources": resources,
    }

    # Write config file
    output_dir.mkdir(parents=True, exist_ok=True)
    config_path = output_dir / f"phate_{name}.yaml"

    with open(config_path, "w") as f:
        # Write package directive (must come first)
        f.write("# @package _global_\n\n")

        # Write header
        f.write(f"# PHATE experiment: {name}\n")
        f.write(f"# Generated from geomancer-ml-decision-making config\n")
        f.write(f"# Label key: {label_key}\n")
        f.write(f"# H5AD: {h5ad_path}\n\n")

        # Write basic fields
        f.write(f"name: {ml_config['name']}\n")
        f.write(f"seed: {ml_config['seed']}\n")
        f.write(f"project: {ml_config['project']}\n\n")

        # Write defaults section (proper Hydra format)
        f.write("defaults:\n")
        for default in ml_config["defaults"]:
            f.write(f"  - {default}\n")
        f.write("\n")

        # Write algorithms section
        f.write("algorithms:\n")
        f.write("  latent:\n")
        for key, value in ml_config["algorithms"]["latent"].items():
            f.write(f"    {key}: {value}\n")
        f.write("\n")

        # Write data section
        f.write("data:\n")
        f.write(f"  adata_path: {ml_config['data']['adata_path']}\n")
        f.write(f"  test_split: {ml_config['data']['test_split']}\n")
        f.write("  _metadata_:\n")
        f.write(f"    label_key: {label_key}\n")
        f.write(f"    extract_metadata: {ml_config['data']['_metadata_']['extract_metadata']}\n")
        f.write("\n")

        # Write callbacks section if output_dir specified
        if "callbacks" in ml_config:
            f.write("callbacks:\n")
            f.write("  embedding:\n")
            f.write(f"    output_dir: {ml_config['callbacks']['embedding']['output_dir']}\n")
            f.write("\n")

    return config_path, metadata


def generate_all_configs(
    user_config: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Generate all ManyLatents configs from user config.

    Args:
        user_config: Loaded user config dict.
        output_dir: Directory for generated configs. Defaults to
                    <manylatents>/configs/experiment/custom/.

    Returns:
        Manifest dict with info about all generated configs.
    """
    if output_dir is None:
        manylatents_dir = Path(user_config.get("manylatents_dir", "/home/btd8/manylatents"))
        output_dir = manylatents_dir / "manylatents" / "configs" / "experiment" / "custom"

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "cluster": user_config.get("cluster", "yale"),
        "experiments": [],
        "output_dir": str(output_dir),
    }

    for exp in user_config.get("experiments", []):
        try:
            config_path, metadata = generate_experiment_config(
                user_config, exp, output_dir
            )
            metadata["config_path"] = str(config_path)
            manifest["experiments"].append(metadata)
            logger.info(f"Generated config: {config_path}")
        except Exception as e:
            logger.error(f"Failed to generate config for {exp.get('name', 'unknown')}: {e}")
            manifest["experiments"].append({
                "name": exp.get("name", "unknown"),
                "error": str(e),
            })

    # Save manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"Saved manifest to {manifest_path}")

    return manifest


def get_hydra_submit_command(
    manifest: dict[str, Any],
    cluster: str | None = None,
) -> str:
    """
    Generate the Hydra MULTIRUN command for submitting all experiments.

    Args:
        manifest: The manifest dict from generate_all_configs.
        cluster: Cluster config to use. Defaults to manifest cluster.

    Returns:
        The command string to run.
    """
    cluster = cluster or manifest.get("cluster", "yale")

    # Collect experiment names
    exp_names = [
        exp["name"] for exp in manifest["experiments"]
        if "error" not in exp
    ]

    if not exp_names:
        return "# No valid experiments to run"

    # Build experiment glob pattern
    exp_patterns = ",".join([f"custom/phate_{name}" for name in exp_names])

    return (
        f"cd {manifest['output_dir'].replace('/configs/experiment/custom', '')} && "
        f"python -m manylatents.main experiment={exp_patterns} cluster={cluster}"
    )


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Generate ManyLatents configs from user config"
    )
    parser.add_argument(
        "config",
        type=Path,
        help="Path to phate_experiments.yaml config file",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        help="Output directory for generated configs",
    )
    parser.add_argument(
        "--print-command",
        action="store_true",
        help="Print the Hydra submit command",
    )

    args = parser.parse_args()

    # Load user config
    user_config = load_user_config(args.config)

    # Generate configs
    manifest = generate_all_configs(user_config, args.output_dir)

    # Print summary
    print(f"\nGenerated {len([e for e in manifest['experiments'] if 'error' not in e])} configs")
    print(f"Output directory: {manifest['output_dir']}")

    if args.print_command:
        cmd = get_hydra_submit_command(manifest)
        print(f"\nHydra submit command:\n{cmd}")


if __name__ == "__main__":
    main()
