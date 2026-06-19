"""Generate UTM/km maps from canonical logit Kriging grid predictions."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize
from pyproj import Transformer
from scipy.special import expit


ROOT = Path(__file__).resolve().parents[1]
PRED_CSV = ROOT / "results/logit_predictions_utm_grid100.csv"
TRAIN_CSV = ROOT / "data/delta_0.05_utm.csv"
BOUNDARY = ROOT / "data/rs_boundary.geojson"
OUT_DIR = ROOT / "results"
Z95 = 1.959963984540054


def load_no_header(path: Path) -> np.ndarray:
    arr = np.genfromtxt(path, delimiter=",")
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr


def iter_boundary_rings(geojson: dict):
    geom = geojson["features"][0]["geometry"]
    if geom["type"] == "Polygon":
        for ring in geom["coordinates"]:
            yield ring
    elif geom["type"] == "MultiPolygon":
        for polygon in geom["coordinates"]:
            for ring in polygon:
                yield ring
    else:
        raise ValueError(f"unsupported geometry type: {geom['type']}")


def boundary_utm_km() -> list[np.ndarray]:
    if not BOUNDARY.exists():
        return []
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:31982", always_xy=True)
    with open(BOUNDARY) as f:
        geojson = json.load(f)
    rings = []
    for ring in iter_boundary_rings(geojson):
        lon = np.array([p[0] for p in ring], dtype=float)
        lat = np.array([p[1] for p in ring], dtype=float)
        x, y = transformer.transform(lon, lat)
        rings.append(np.column_stack([np.asarray(x) / 1000.0, np.asarray(y) / 1000.0]))
    return rings


def add_boundary(ax: plt.Axes, rings: list[np.ndarray]) -> None:
    for ring in rings:
        ax.plot(ring[:, 0], ring[:, 1], color="black", linewidth=1.1, zorder=5)


def add_scale_bar(ax: plt.Axes, length_km: float = 100.0) -> None:
    xmin, xmax = ax.get_xlim()
    ymin, ymax = ax.get_ylim()
    x0 = xmin + 0.07 * (xmax - xmin)
    y0 = ymin + 0.07 * (ymax - ymin)
    ax.plot([x0, x0 + length_km], [y0, y0], color="black", linewidth=3, zorder=6)
    ax.plot([x0, x0], [y0 - 5, y0 + 5], color="black", linewidth=2, zorder=6)
    ax.plot(
        [x0 + length_km, x0 + length_km],
        [y0 - 5, y0 + 5],
        color="black",
        linewidth=2,
        zorder=6,
    )
    ax.text(
        x0 + length_km / 2,
        y0 + 10,
        f"{length_km:.0f} km",
        ha="center",
        va="bottom",
        fontsize=9,
        color="black",
        zorder=6,
    )


def save_dual(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    fig.savefig(path.with_suffix(".svg"), format="svg", bbox_inches="tight")
    print(f"saved {path}")
    print(f"saved {path.with_suffix('.svg')}")


def format_utm_axis(ax: plt.Axes, rings: list[np.ndarray]) -> None:
    add_boundary(ax, rings)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("UTM Easting (km, SIRGAS 2000 / UTM 22S)")
    ax.set_ylabel("UTM Northing (km, SIRGAS 2000 / UTM 22S)")
    ax.grid(color="0.85", linewidth=0.5, alpha=0.8)
    add_scale_bar(ax)


def plot_single(
    x_grid: np.ndarray,
    y_grid: np.ndarray,
    z: np.ndarray,
    train: np.ndarray,
    rings: list[np.ndarray],
    title: str,
    colorbar_label: str,
    cmap: str,
    path: Path,
    norm: Normalize | None = None,
) -> None:
    fig, ax = plt.subplots(figsize=(9, 8))
    mesh = ax.pcolormesh(
        x_grid,
        y_grid,
        z.reshape(len(y_grid), len(x_grid)),
        cmap=cmap,
        norm=norm,
        shading="auto",
        alpha=0.86,
    )
    ax.scatter(train[:, 0], train[:, 1], c="black", s=1.0, alpha=0.24, linewidths=0)
    cbar = fig.colorbar(mesh, ax=ax, shrink=0.78, pad=0.02)
    cbar.set_label(colorbar_label)
    ax.set_title(title)
    format_utm_axis(ax, rings)
    save_dual(fig, path)
    plt.close(fig)


def main() -> None:
    pred = load_no_header(PRED_CSV)
    train = load_no_header(TRAIN_CSV)

    x_grid = np.unique(pred[:, 0])
    y_grid = np.unique(pred[:, 1])
    expected = len(x_grid) * len(y_grid)
    if expected != len(pred):
        raise ValueError(f"prediction grid is not rectangular: {len(pred)} != {expected}")

    pred_p = expit(pred[:, 2])
    sd_logit = np.sqrt(np.maximum(pred[:, 3], 0.0))
    interval_width = expit(pred[:, 2] + Z95 * sd_logit) - expit(
        pred[:, 2] - Z95 * sd_logit
    )
    rings = boundary_utm_km()

    plot_single(
        x_grid,
        y_grid,
        pred_p,
        train,
        rings,
        "Logit Kriging Connectivity Probability",
        "Predicted probability",
        "RdYlGn",
        OUT_DIR / "logit_utm_connectivity_map.png",
        Normalize(vmin=0.0, vmax=1.0),
    )
    plot_single(
        x_grid,
        y_grid,
        interval_width,
        train,
        rings,
        "Logit Kriging Prediction Uncertainty",
        "Prediction uncertainty",
        "YlOrRd",
        OUT_DIR / "logit_utm_uncertainty_map.png",
        Normalize(vmin=0.0, vmax=1.0),
    )

    fig, axes = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    sc = axes[0].scatter(
        train[:, 0],
        train[:, 1],
        c=train[:, 2],
        s=4,
        cmap="RdYlGn",
        norm=Normalize(vmin=0.0, vmax=1.0),
        alpha=0.85,
        linewidths=0,
    )
    axes[0].set_title("Observed Cell Proportions")
    fig.colorbar(sc, ax=axes[0], shrink=0.72, pad=0.02).set_label("Proportion")

    im = axes[1].pcolormesh(
        x_grid,
        y_grid,
        pred_p.reshape(len(y_grid), len(x_grid)),
        cmap="RdYlGn",
        norm=Normalize(vmin=0.0, vmax=1.0),
        shading="auto",
        alpha=0.86,
    )
    axes[1].set_title("Predicted Probability")
    fig.colorbar(im, ax=axes[1], shrink=0.72, pad=0.02).set_label("Probability")

    im = axes[2].pcolormesh(
        x_grid,
        y_grid,
        interval_width.reshape(len(y_grid), len(x_grid)),
        cmap="YlOrRd",
        norm=Normalize(vmin=0.0, vmax=1.0),
        shading="auto",
        alpha=0.86,
    )
    axes[2].set_title("Prediction Uncertainty")
    fig.colorbar(im, ax=axes[2], shrink=0.72, pad=0.02).set_label(
        "Prediction uncertainty"
    )

    for ax in axes:
        format_utm_axis(ax, rings)

    save_dual(fig, OUT_DIR / "logit_utm_panel.png")
    plt.close(fig)

    print("=== logit UTM map summary ===")
    print(f"grid={len(x_grid)}x{len(y_grid)} points={len(pred)}")
    print(f"pred_p min={pred_p.min():.8f} max={pred_p.max():.8f}")
    print(f"interval_width min={interval_width.min():.8f} max={interval_width.max():.8f}")
    print("DONE")


if __name__ == "__main__":
    main()
