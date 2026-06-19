"""Validation framework: cross-validation, metrics, and comparison with Röpke."""

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class PredictionMetrics:
    """Prediction quality metrics."""

    rmse: float
    mae: float
    bias: float
    coverage_95: Optional[float]  # Fraction of true values within 95% interval
    n_points: int

    def __str__(self) -> str:
        lines = [
            f"RMSE:         {self.rmse:.6f}",
            f"MAE:          {self.mae:.6f}",
            f"Bias:         {self.bias:.6f}",
            f"N points:     {self.n_points}",
        ]
        if self.coverage_95 is not None:
            lines.append(f"Coverage 95%: {self.coverage_95:.4f}")
        return "\n".join(lines)


def compute_metrics(
    observed: np.ndarray,
    predicted: np.ndarray,
    pred_variance: Optional[np.ndarray] = None,
) -> PredictionMetrics:
    """Compute prediction quality metrics.

    Args:
        observed: True values.
        predicted: Predicted values.
        pred_variance: Kriging variance (optional, for coverage computation).
    """
    residuals = observed - predicted
    n = len(observed)

    rmse = float(np.sqrt(np.mean(residuals**2)))
    mae = float(np.mean(np.abs(residuals)))
    bias = float(np.mean(residuals))

    coverage = None
    if pred_variance is not None:
        pred_std = np.sqrt(pred_variance)
        lower = predicted - 1.96 * pred_std
        upper = predicted + 1.96 * pred_std
        in_interval = (observed >= lower) & (observed <= upper)
        coverage = float(np.mean(in_interval))

    return PredictionMetrics(
        rmse=rmse, mae=mae, bias=bias, coverage_95=coverage, n_points=n
    )


class SpatialBlockCV:
    """Spatial block cross-validation for honest evaluation of spatial models.

    Divides the spatial domain into a grid of blocks. Each fold holds out
    all cells in one block and trains on the rest.
    """

    def __init__(
        self,
        data_csv: Path,
        n_blocks_lat: int = 5,
        n_blocks_lon: int = 5,
        output_dir: Path = Path("preprocessing/output/cv_splits"),
    ):
        self.data_csv = data_csv
        self.n_blocks_lat = n_blocks_lat
        self.n_blocks_lon = n_blocks_lon
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _load_data(self) -> np.ndarray:
        """Load CSV data as numpy array (x, y, measurement)."""
        rows = []
        with open(self.data_csv) as f:
            reader = csv.reader(f)
            for row in reader:
                rows.append([float(v) for v in row])
        return np.array(rows)

    def generate_folds(self) -> list[tuple[Path, Path]]:
        """Generate train/test CSV pairs for each spatial block fold.

        Returns list of (train_csv_path, test_csv_path) tuples.
        """
        data = self._load_data()
        x, y = data[:, 0], data[:, 1]

        x_min, x_max = x.min(), x.max()
        y_min, y_max = y.min(), y.max()

        x_edges = np.linspace(x_min, x_max, self.n_blocks_lon + 1)
        y_edges = np.linspace(y_min, y_max, self.n_blocks_lat + 1)

        # Assign each point to a block
        x_block = np.clip(
            np.digitize(x, x_edges[1:-1]), 0, self.n_blocks_lon - 1
        )
        y_block = np.clip(
            np.digitize(y, y_edges[1:-1]), 0, self.n_blocks_lat - 1
        )
        block_id = y_block * self.n_blocks_lon + x_block

        n_folds = self.n_blocks_lat * self.n_blocks_lon
        fold_paths = []

        for fold in range(n_folds):
            test_mask = block_id == fold
            if test_mask.sum() == 0:
                continue  # Skip empty blocks

            train_mask = ~test_mask
            train_data = data[train_mask]
            test_data = data[test_mask]

            train_path = self.output_dir / f"fold_{fold:02d}_train.csv"
            test_path = self.output_dir / f"fold_{fold:02d}_test.csv"

            np.savetxt(train_path, train_data, delimiter=",", fmt="%.10f")
            np.savetxt(test_path, test_data, delimiter=",", fmt="%.10f")

            fold_paths.append((train_path, test_path))

        return fold_paths


def ropke_baseline(
    data_csv: Path, test_csv: Path
) -> PredictionMetrics:
    """Compute Röpke's quadrant method baseline.

    For test points, the "prediction" is simply the proportion of the
    nearest training cell. This approximates Röpke's approach where each
    cell's proportion stands on its own without spatial interpolation.

    Args:
        data_csv: Full aggregated CSV (x, y, measurement).
        test_csv: Test split CSV (x, y, measurement).

    Returns:
        Metrics comparing test observations vs nearest-cell predictions.
    """
    train_data = []
    with open(data_csv) as f:
        for row in csv.reader(f):
            train_data.append([float(v) for v in row])
    train = np.array(train_data)

    test_data = []
    with open(test_csv) as f:
        for row in csv.reader(f):
            test_data.append([float(v) for v in row])
    test = np.array(test_data)

    # For each test point, find nearest training point (brute force, fine for ~50K)
    predicted = np.zeros(len(test))
    for i in range(len(test)):
        dx = train[:, 0] - test[i, 0]
        dy = train[:, 1] - test[i, 1]
        dists = dx**2 + dy**2
        nearest = np.argmin(dists)
        predicted[i] = train[nearest, 2]

    return compute_metrics(test[:, 2], predicted)


def inverse_logit(values: np.ndarray) -> np.ndarray:
    """Inverse logit (sigmoid) transform: p = 1 / (1 + exp(-x))."""
    return 1.0 / (1.0 + np.exp(-values))
