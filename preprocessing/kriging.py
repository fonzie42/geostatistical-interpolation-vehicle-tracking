"""Python Kriging prediction using parameters estimated by ExaGeoStatCPP.

ExaGeoStatCPP estimates Matérn covariance parameters via MLE but does not
export predicted values through its CLI. This module implements Ordinary
Kriging in Python using scipy, applying the theta parameters that ExaGeoStatCPP
estimated. This gives us full control over the prediction grid for map generation.

Workflow:
    1. ExaGeoStatCPP: MLE → (sigma², beta, nu, nugget)
    2. This module: build covariance matrix with those params → predict on grid
"""

import csv
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.spatial.distance import cdist
from scipy.special import gamma, kv


@dataclass
class MaternParams:
    """Matérn covariance parameters as estimated by ExaGeoStatCPP.

    The univariate_matern_nuggets_stationary kernel uses:
        C(h) = sigma2 * (2^(1-nu) / Gamma(nu)) * (h/beta)^nu * K_nu(h/beta) + nugget*I

    Attributes:
        sigma2: Variance (amplitude) parameter.
        beta: Range (spatial correlation length) parameter.
        nu: Smoothness parameter.
        nugget: Nugget (measurement noise) variance. Zero if no nugget kernel.
    """

    sigma2: float
    beta: float
    nu: float
    nugget: float = 0.0


def matern_covariance(h: np.ndarray, params: MaternParams) -> np.ndarray:
    """Compute Matérn covariance for distance array h.

    Args:
        h: Array of pairwise distances (non-negative).
        params: Matérn parameters.

    Returns:
        Covariance values (same shape as h).
    """
    sigma2, beta, nu = params.sigma2, params.beta, params.nu

    result = np.zeros_like(h, dtype=float)
    nonzero = h > 0

    scaled = h[nonzero] / beta
    factor = (sigma2 * (2 ** (1 - nu)) / gamma(nu))
    result[nonzero] = factor * (scaled ** nu) * kv(nu, scaled)
    result[~nonzero] = sigma2 + params.nugget

    return result


def build_covariance_matrix(
    locs: np.ndarray, params: MaternParams
) -> np.ndarray:
    """Build the full covariance matrix for a set of locations.

    Args:
        locs: (N, 2) array of (x, y) coordinates.
        params: Matérn parameters.

    Returns:
        (N, N) covariance matrix.
    """
    dists = cdist(locs, locs, metric="euclidean")
    C = matern_covariance(dists, params)
    return C


def kriging_predict(
    train_locs: np.ndarray,
    train_vals: np.ndarray,
    pred_locs: np.ndarray,
    params: MaternParams,
    batch_size: int = 500,
) -> tuple[np.ndarray, np.ndarray]:
    """Ordinary Kriging prediction using Matérn covariance.

    Args:
        train_locs: (N, 2) training locations.
        train_vals: (N,) training measurements.
        pred_locs: (M, 2) prediction locations.
        params: Matérn covariance parameters (from ExaGeoStatCPP MLE).
        batch_size: Process prediction points in batches to limit memory.

    Returns:
        (predictions, variances, elapsed_seconds): predictions and variances
        are shape (M,), elapsed_seconds is the wall-clock time in seconds.
    """
    n_train = len(train_locs)
    n_pred = len(pred_locs)

    t0 = time.monotonic()

    # Build training covariance matrix (N x N)
    C_train = build_covariance_matrix(train_locs, params)

    # Cholesky factorization for solving
    L = np.linalg.cholesky(C_train)

    predictions = np.zeros(n_pred)
    variances = np.zeros(n_pred)

    # Process in batches to manage memory
    for start in range(0, n_pred, batch_size):
        end = min(start + batch_size, n_pred)
        batch_locs = pred_locs[start:end]

        # Cross-covariance: C(train, pred_batch)
        dists_cross = cdist(train_locs, batch_locs, metric="euclidean")
        c_cross = matern_covariance(dists_cross, params)

        # Solve C_train * weights = c_cross using Cholesky
        # L * L^T * W = c_cross  =>  L * y = c_cross, then L^T * W = y
        y = np.linalg.solve(L, c_cross)
        weights = np.linalg.solve(L.T, y)

        # Predictions: z_pred = W^T * z_train
        predictions[start:end] = weights.T @ train_vals

        # Kriging variance: sigma2 + nugget - c_cross^T * C_train^{-1} * c_cross
        c0 = params.sigma2 + params.nugget
        for i in range(end - start):
            variances[start + i] = c0 - np.dot(c_cross[:, i], weights[:, i])

    # Clamp negative variances (numerical artifact)
    variances = np.maximum(variances, 0.0)

    elapsed = time.monotonic() - t0

    return predictions, variances, elapsed


def load_csv_data(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load ExaGeoStatCPP format CSV (no header: x, y, measurement).

    Returns:
        (locations, values): locations is (N,2), values is (N,).
    """
    rows = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([float(v) for v in row])
    data = np.array(rows)
    return data[:, :2], data[:, 2]


def make_prediction_grid(
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    resolution: int = 100,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Create a regular grid for prediction.

    Args:
        x_min, x_max, y_min, y_max: Grid bounds.
        resolution: Number of grid points along each axis.

    Returns:
        (grid_locs, x_grid, y_grid): grid_locs is (resolution^2, 2),
        x_grid and y_grid are 1D arrays of length resolution.
    """
    x_grid = np.linspace(x_min, x_max, resolution)
    y_grid = np.linspace(y_min, y_max, resolution)
    xx, yy = np.meshgrid(x_grid, y_grid)
    grid_locs = np.column_stack([xx.ravel(), yy.ravel()])
    return grid_locs, x_grid, y_grid
