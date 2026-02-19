#!/usr/bin/env python3
"""
SLURM job script template generator for any algorithm.

This module generates SLURM job scripts for running dimensionality reduction
experiments on a cluster.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from string import Template
from dataclasses import dataclass


# Default SLURM template
DEFAULT_SLURM_TEMPLATE = """#!/bin/bash
#SBATCH --job-name=${job_name}
#SBATCH --output=${log_dir}/${algorithm}_%A_%a.out
#SBATCH --error=${log_dir}/${algorithm}_%A_%a.err
#SBATCH --array=${array_range}
#SBATCH --cpus-per-task=${cpus}
#SBATCH --mem=${mem}
#SBATCH --time=${time}
#SBATCH --partition=${partition}

# Exit on error
set -e

# Create output and logs directories
mkdir -p ${log_dir}
mkdir -p ${output_dir}

# Activate virtual environment
export PATH="$HOME/.local/bin:$PATH"
cd ${manylatents_dir}
source .venv/bin/activate

# Read experiment list
EXPERIMENT_LIST="${experiment_list}"

# Extract experiment name for this array task
EXPERIMENT_NAME=$(python3 -c "
import yaml
import sys
with open('${EXPERIMENT_LIST}', 'r') as f:
    data = yaml.safe_load(f)
    experiments = data['experiments']
    if ${SLURM_ARRAY_TASK_ID} < len(experiments):
        print(experiments[${SLURM_ARRAY_TASK_ID}]['name'])
    else:
        sys.exit(1)
")

if [ -z "$EXPERIMENT_NAME" ]; then
    echo "Error: Could not find experiment for task ID ${SLURM_ARRAY_TASK_ID}"
    exit 1
fi

echo "========================================="
echo "Running experiment: ${EXPERIMENT_NAME}"
echo "Task ID: ${SLURM_ARRAY_TASK_ID}"
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "========================================="

# Run the experiment
python3 -m manylatents.main \\
    experiment=cellxgene/${EXPERIMENT_NAME} \\
    logger=none \\
    hydra.run.dir=${output_dir}/${EXPERIMENT_NAME}

echo "========================================="
echo "Experiment completed: ${EXPERIMENT_NAME}"
echo "Date: $(date)"
echo "========================================="
"""


@dataclass
class SlurmResources:
    """Resource requirements for SLURM jobs."""
    mem: str = "32G"
    cpus: int = 4
    time: str = "4:00:00"
    partition: str = "day"

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "SlurmResources":
        """Create from dictionary."""
        return cls(
            mem=config.get("mem", "32G"),
            cpus=config.get("cpus", 4),
            time=config.get("time", "4:00:00"),
            partition=config.get("partition", "day"),
        )


class SlurmJobGenerator:
    """Generate SLURM job scripts for any algorithm."""

    def __init__(
        self,
        algorithm: str,
        manylatents_dir: Path,
        output_base: Path,
        log_dir: Optional[Path] = None,
    ):
        """
        Initialize the SLURM job generator.

        Args:
            algorithm: Algorithm name (e.g., "phate", "umap")
            manylatents_dir: Path to ManyLatents installation
            output_base: Base directory for experiment outputs
            log_dir: Directory for log files (defaults to output_base/logs)
        """
        self.algorithm = algorithm.lower()
        self.manylatents_dir = Path(manylatents_dir)
        self.output_base = Path(output_base)
        self.log_dir = Path(log_dir) if log_dir else self.output_base / "logs"

    def get_template_vars(
        self,
        n_jobs: int,
        resources: Optional[SlurmResources] = None,
    ) -> Dict[str, str]:
        """
        Get template variables for SLURM script.

        Args:
            n_jobs: Number of array jobs
            resources: Optional resource requirements

        Returns:
            Dictionary of template variables
        """
        if resources is None:
            resources = SlurmResources()

        # Calculate array range
        if n_jobs > 1:
            array_range = f"0-{n_jobs-1}%15"  # Max 15 concurrent
        else:
            array_range = "0-0"

        return {
            "job_name": f"{self.algorithm}_cellxgene",
            "algorithm": self.algorithm,
            "log_dir": str(self.log_dir),
            "output_dir": str(self.output_base),
            "manylatents_dir": str(self.manylatents_dir),
            "experiment_list": str(self.manylatents_dir / f"{self.algorithm}_experiments.yaml"),
            "scripts_dir": str(Path(__file__).parent.parent.parent),  # geomancer/scripts directory
            "array_range": array_range,
            "cpus": str(resources.cpus),
            "mem": resources.mem,
            "time": resources.time,
            "partition": resources.partition,
            "SLURM_ARRAY_TASK_ID": "$SLURM_ARRAY_TASK_ID",
        }

    def generate_job_script(
        self,
        n_jobs: int,
        resources: Optional[SlurmResources] = None,
        template: Optional[str] = None,
    ) -> str:
        """
        Generate a SLURM job script.

        Args:
            n_jobs: Number of array jobs
            resources: Optional resource requirements
            template: Optional custom template (uses default if not provided)

        Returns:
            SLURM job script as string
        """
        if template is None:
            # Load algorithm-specific template if available
            template_path = Path(__file__).parent.parent / "algorithms" / self.algorithm / "slurm_job.slurm"
            if template_path.exists():
                template = template_path.read_text()
            else:
                template = DEFAULT_SLURM_TEMPLATE

        vars_dict = self.get_template_vars(n_jobs, resources)
        # Use safe_substitute to handle missing keys
        return Template(template).safe_substitute(vars_dict)

    def write_job_script(
        self,
        output_path: Path,
        n_jobs: int,
        resources: Optional[SlurmResources] = None,
        template: Optional[str] = None,
    ) -> Path:
        """
        Write a SLURM job script to disk.

        Args:
            output_path: Path to write the script
            n_jobs: Number of array jobs
            resources: Optional resource requirements
            template: Optional custom template

        Returns:
            Path to written script
        """
        script_content = self.generate_job_script(n_jobs, resources, template)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(script_content)

        # Make executable
        output_path.chmod(0o755)

        return output_path

    @classmethod
    def for_algorithm(
        cls,
        algorithm: str,
        resources: Optional[Dict[str, Any]] = None,
        manylatents_dir: Path = Path("/home/btd8/manylatents"),
        output_base: Path = Path("/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs"),
    ) -> "SlurmJobGenerator":
        """Create a generator for a specific algorithm."""
        return cls(
            algorithm=algorithm,
            manylatents_dir=manylatents_dir,
            output_base=output_base,
        )


def main():
    """CLI entry point for SLURM script generation."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate SLURM job scripts for algorithm experiments"
    )
    parser.add_argument(
        "--algorithm",
        type=str,
        default="phate",
        help="Algorithm name (default: phate)"
    )
    parser.add_argument(
        "--n-jobs",
        type=int,
        required=True,
        help="Number of array jobs"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output script path (default: slurm_jobs/run_{algorithm}_array.slurm)"
    )
    parser.add_argument(
        "--manylatents-dir",
        type=str,
        default="/home/btd8/manylatents",
        help="Path to ManyLatents installation"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="/nfs/roberts/project/pi_sk2433/shared/Geomancer_2025_Data/manylatents_outputs",
        help="Base output directory for experiments"
    )
    parser.add_argument(
        "--mem",
        type=str,
        default="32G",
        help="Memory per job (default: 32G)"
    )
    parser.add_argument(
        "--cpus",
        type=int,
        default=4,
        help="CPUs per job (default: 4)"
    )
    parser.add_argument(
        "--time",
        type=str,
        default="4:00:00",
        help="Time limit (default: 4:00:00)"
    )
    parser.add_argument(
        "--partition",
        type=str,
        default="day",
        help="SLURM partition (default: day)"
    )

    args = parser.parse_args()

    # Create generator
    generator = SlurmJobGenerator(
        algorithm=args.algorithm,
        manylatents_dir=Path(args.manylatents_dir),
        output_base=Path(args.output_dir),
    )

    # Create resources
    resources = SlurmResources(
        mem=args.mem,
        cpus=args.cpus,
        time=args.time,
        partition=args.partition,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path("slurm_jobs") / f"run_{args.algorithm}_array.slurm"

    # Write script
    generator.write_job_script(output_path, args.n_jobs, resources)

    print(f"Generated SLURM script: {output_path}")
    print(f"  Jobs: {args.n_jobs}")
    print(f"  Resources: {resources.cpus} CPUs, {resources.mem}, {resources.time}")
    print(f"\nTo submit: sbatch {output_path}")


if __name__ == "__main__":
    main()
