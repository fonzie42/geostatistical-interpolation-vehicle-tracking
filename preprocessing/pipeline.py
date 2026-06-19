"""End-to-end preprocessing pipeline orchestration."""

import argparse
import sys
from pathlib import Path

from preprocessing.config import PipelineConfig
from preprocessing.spatial_binning import SpatialBinner


def run_pipeline(config: PipelineConfig) -> dict:
    """Run the full preprocessing pipeline and return summary statistics.

    Returns a dict with: n_cells, n_total_events, proportion_mean,
    proportion_std, proportion_min, proportion_max, output_path.
    """
    binner = SpatialBinner(config)
    df = binner.run()

    stats = {
        "n_cells": len(df),
        "n_total_events": df["n_events"].sum(),
        "proportion_mean": df["proportion"].mean(),
        "proportion_std": df["proportion"].std(),
        "proportion_min": df["proportion"].min(),
        "proportion_max": df["proportion"].max(),
        "output_path": str(config.output_path),
    }

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess GPS connectivity data for ExaGeoStatCPP Kriging."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PipelineConfig.input_path,
        help="Path to input Parquet file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PipelineConfig.output_path,
        help="Path for output CSV.",
    )
    parser.add_argument(
        "--delta",
        type=float,
        default=0.01,
        help="Grid cell size in degrees (default: 0.01, ~1.1km).",
    )
    parser.add_argument(
        "--min-events",
        type=int,
        default=30,
        help="Minimum events per cell for inclusion (default: 30).",
    )
    parser.add_argument(
        "--logit",
        action="store_true",
        help="Apply logit transform to proportions.",
    )

    args = parser.parse_args()

    config = PipelineConfig(
        input_path=args.input,
        output_path=args.output,
        delta=args.delta,
        min_events=args.min_events,
        apply_logit=args.logit,
    )

    print(f"Running preprocessing pipeline:")
    print(f"  Input:      {config.input_path}")
    print(f"  Output:     {config.output_path}")
    print(f"  Delta:      {config.delta} degrees")
    print(f"  Min events: {config.min_events}")
    print(f"  Logit:      {config.apply_logit}")
    print()

    stats = run_pipeline(config)

    print(f"Pipeline complete:")
    print(f"  Cells:           {stats['n_cells']}")
    print(f"  Total events:    {stats['n_total_events']}")
    print(f"  Proportion mean: {stats['proportion_mean']:.4f}")
    print(f"  Proportion std:  {stats['proportion_std']:.4f}")
    print(f"  Proportion range: [{stats['proportion_min']:.4f}, {stats['proportion_max']:.4f}]")
    print(f"  Output:          {stats['output_path']}")


if __name__ == "__main__":
    main()
