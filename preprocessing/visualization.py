"""Visualization module for Kriging prediction maps.

Generates "weather-map" style heatmaps showing predicted connectivity probability
and uncertainty across the RS road network. Uses matplotlib for rendering.
Optionally adds geographic base map tiles via contextily.

The maps show:
    1. Connectivity probability surface (0=offline to 1=online)
    2. Prediction uncertainty surface (kriging standard deviation)
    3. Training data overlay (observed cell locations)

All plot functions save both PNG (150 dpi) and SVG formats.
"""

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize

import json

try:
    import contextily as ctx

    HAS_CONTEXTILY = True
except ImportError:
    HAS_CONTEXTILY = False


# EPSG:4326 (lat/lon) tile provider that works without reprojection
_TILE_SOURCE = ctx.providers.OpenStreetMap.Mapnik if HAS_CONTEXTILY else None

# Path to RS boundary GeoJSON (downloaded from IBGE)
_RS_BOUNDARY_PATH = Path(__file__).parent.parent / "data" / "rs_boundary.geojson"


def _save_dual(fig: plt.Figure, output_path: Path) -> None:
    """Save figure in both PNG and SVG formats."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    svg_path = output_path.with_suffix(".svg")
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    print(f"Saved: {output_path}")
    print(f"Saved: {svg_path}")


def _add_basemap(ax: plt.Axes, alpha: float = 0.3) -> None:
    """Add OpenStreetMap base map tiles if contextily is available."""
    if not HAS_CONTEXTILY:
        return
    try:
        ctx.add_basemap(
            ax,
            crs="EPSG:4326",
            source=_TILE_SOURCE,
            alpha=alpha,
            attribution_size=6,
        )
    except Exception as e:
        print(f"Warning: could not add basemap ({e}), continuing without it")


def _add_rs_boundary(ax: plt.Axes, color: str = "black", linewidth: float = 1.5) -> None:
    """Add RS state boundary outline from GeoJSON."""
    if not _RS_BOUNDARY_PATH.exists():
        return
    try:
        with open(_RS_BOUNDARY_PATH) as f:
            geojson = json.load(f)
        coords = geojson["features"][0]["geometry"]["coordinates"][0]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        ax.plot(xs, ys, color=color, linewidth=linewidth, zorder=5)
    except Exception as e:
        print(f"Warning: could not add RS boundary ({e})")


def plot_prediction_map(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    predictions: np.ndarray,
    train_locs: Optional[np.ndarray] = None,
    title: str = "Predicted Connectivity Probability",
    cmap: str = "RdYlGn",
    vmin: float = 0.0,
    vmax: float = 1.0,
    output_path: Optional[Path] = None,
    figsize: tuple = (12, 10),
    basemap: bool = True,
    boundary: bool = True,
) -> plt.Figure:
    """Plot a heatmap of predicted values on a regular grid.

    Args:
        x_grid: 1D array of x coordinates (longitude).
        y_grid: 1D array of y coordinates (latitude).
        predictions: 1D array of length len(x_grid)*len(y_grid), row-major.
        train_locs: (N, 2) training locations to overlay as dots.
        title: Plot title.
        cmap: Matplotlib colormap name.
        vmin, vmax: Color scale bounds.
        output_path: If set, save figure to this path (PNG + SVG).
        figsize: Figure size in inches.
        basemap: Whether to add OpenStreetMap base map tiles.

    Returns:
        matplotlib Figure object.
    """
    Z = predictions.reshape(len(y_grid), len(x_grid))

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    im = ax.pcolormesh(
        x_grid, y_grid, Z,
        cmap=cmap,
        norm=Normalize(vmin=vmin, vmax=vmax),
        shading="auto",
        alpha=0.8,
    )
    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Connectivity Probability", fontsize=12)

    if train_locs is not None:
        ax.scatter(
            train_locs[:, 0], train_locs[:, 1],
            c="black", s=1, alpha=0.3, label="Observed cells",
        )
        ax.legend(loc="upper right", fontsize=9)

    if basemap:
        _add_basemap(ax)
    if boundary:
        _add_rs_boundary(ax)

    ax.set_xlabel("Longitude", fontsize=12)
    ax.set_ylabel("Latitude", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.set_aspect("equal")

    if output_path:
        _save_dual(fig, output_path)

    return fig


def plot_uncertainty_map(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    variances: np.ndarray,
    train_locs: Optional[np.ndarray] = None,
    title: str = "Prediction Uncertainty (Kriging Std Dev)",
    output_path: Optional[Path] = None,
    figsize: tuple = (12, 10),
    basemap: bool = True,
    boundary: bool = True,
) -> plt.Figure:
    """Plot kriging uncertainty (standard deviation) as a heatmap.

    Args:
        x_grid: 1D array of x coordinates.
        y_grid: 1D array of y coordinates.
        variances: 1D array of kriging variances, length len(x_grid)*len(y_grid).
        train_locs: Training locations to overlay.
        title: Plot title.
        output_path: If set, save figure to this path (PNG + SVG).
        figsize: Figure size.
        basemap: Whether to add OpenStreetMap base map tiles.

    Returns:
        matplotlib Figure object.
    """
    std_dev = np.sqrt(variances).reshape(len(y_grid), len(x_grid))

    fig, ax = plt.subplots(1, 1, figsize=figsize)
    im = ax.pcolormesh(
        x_grid, y_grid, std_dev,
        cmap="YlOrRd",
        shading="auto",
        alpha=0.8,
    )
    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Standard Deviation", fontsize=12)

    if train_locs is not None:
        ax.scatter(
            train_locs[:, 0], train_locs[:, 1],
            c="black", s=1, alpha=0.3, label="Observed cells",
        )
        ax.legend(loc="upper right", fontsize=9)

    if basemap:
        _add_basemap(ax)
    if boundary:
        _add_rs_boundary(ax)

    ax.set_xlabel("Longitude", fontsize=12)
    ax.set_ylabel("Latitude", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.set_aspect("equal")

    if output_path:
        _save_dual(fig, output_path)

    return fig


def plot_observed_data(
    locs: np.ndarray,
    values: np.ndarray,
    title: str = "Observed Connectivity Proportions",
    cmap: str = "RdYlGn",
    vmin: float = 0.0,
    vmax: float = 1.0,
    output_path: Optional[Path] = None,
    figsize: tuple = (12, 10),
    basemap: bool = True,
    boundary: bool = True,
) -> plt.Figure:
    """Scatter plot of observed data points colored by value.

    Args:
        locs: (N, 2) array of (x, y) coordinates.
        values: (N,) measurement values.
        title: Plot title.
        cmap: Colormap name.
        vmin, vmax: Color bounds.
        output_path: If set, save figure (PNG + SVG).
        figsize: Figure size.
        basemap: Whether to add OpenStreetMap base map tiles.

    Returns:
        matplotlib Figure object.
    """
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    sc = ax.scatter(
        locs[:, 0], locs[:, 1],
        c=values, cmap=cmap, s=8, alpha=0.8,
        norm=Normalize(vmin=vmin, vmax=vmax),
    )
    cbar = fig.colorbar(sc, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Connectivity Proportion", fontsize=12)

    if basemap:
        _add_basemap(ax)
    if boundary:
        _add_rs_boundary(ax)

    ax.set_xlabel("Longitude", fontsize=12)
    ax.set_ylabel("Latitude", fontsize=12)
    ax.set_title(title, fontsize=14)
    ax.set_aspect("equal")

    if output_path:
        _save_dual(fig, output_path)

    return fig


def plot_comparison_panel(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    predictions: np.ndarray,
    variances: np.ndarray,
    train_locs: np.ndarray,
    train_vals: np.ndarray,
    output_path: Optional[Path] = None,
    figsize: tuple = (20, 7),
    basemap: bool = True,
    boundary: bool = True,
) -> plt.Figure:
    """Three-panel figure: observed data, prediction, uncertainty.

    This is the main visualization output for the thesis.

    Args:
        x_grid, y_grid: Grid coordinates.
        predictions: Predicted values on grid.
        variances: Kriging variances on grid.
        train_locs: (N, 2) training locations.
        train_vals: (N,) training values.
        output_path: Save path (PNG + SVG).
        figsize: Figure size.
        basemap: Whether to add OpenStreetMap base map tiles.

    Returns:
        matplotlib Figure object.
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize)

    # Panel 1: Observed data
    ax = axes[0]
    sc = ax.scatter(
        train_locs[:, 0], train_locs[:, 1],
        c=train_vals, cmap="RdYlGn", s=4, alpha=0.8,
        norm=Normalize(vmin=0, vmax=1),
    )
    fig.colorbar(sc, ax=ax, shrink=0.7)
    ax.set_title("Observed Proportions", fontsize=12)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    if basemap:
        _add_basemap(ax, alpha=0.2)
    if boundary:
        _add_rs_boundary(ax)

    # Panel 2: Predictions
    ax = axes[1]
    Z_pred = predictions.reshape(len(y_grid), len(x_grid))
    im = ax.pcolormesh(
        x_grid, y_grid, Z_pred,
        cmap="RdYlGn", norm=Normalize(vmin=0, vmax=1),
        shading="auto", alpha=0.8,
    )
    fig.colorbar(im, ax=ax, shrink=0.7)
    ax.set_title("Kriging Prediction", fontsize=12)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    if basemap:
        _add_basemap(ax, alpha=0.2)
    if boundary:
        _add_rs_boundary(ax)

    # Panel 3: Uncertainty
    ax = axes[2]
    Z_std = np.sqrt(variances).reshape(len(y_grid), len(x_grid))
    im = ax.pcolormesh(
        x_grid, y_grid, Z_std,
        cmap="YlOrRd", shading="auto", alpha=0.8,
    )
    fig.colorbar(im, ax=ax, shrink=0.7)
    ax.set_title("Prediction Uncertainty (Std Dev)", fontsize=12)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    if basemap:
        _add_basemap(ax, alpha=0.2)
    if boundary:
        _add_rs_boundary(ax)

    plt.tight_layout()

    if output_path:
        _save_dual(fig, output_path)

    return fig
