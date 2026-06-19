"""Regenerate the three native-scale three-panel comparison figures used in the
thesis: Universal/detrended Kriging, Indicator Kriging, and native Kriging at
delta=0.02 (figures 5.6, 5.7, 5.9).

Each figure (observations | Kriging prediction | prediction uncertainty) is drawn
by preprocessing.visualization.plot_comparison_panel from the committed full-grid
prediction CSVs in results/ (100x100 regular grids of x, y, prediction, variance)
and the corresponding aggregated input data in data/.

Notes on the two non-obvious steps, preserved from the original generation:
  - Detrended: the committed predictions_rs_detrended.csv holds the *residual*
    field; the final prediction adds back the quadratic spatial trend whose
    coefficients are in data/trend_coeffs_delta_0.05.csv.
  - Indicator: its observation panel uses the raw binary sample
    (binary_sample_5401.csv), not the aggregated proportions used by the others.
  - Maps use boundary only (basemap=False), matching the thesis figures.

Run from repo root:  .venv/bin/python3 preprocessing/generate_native_panels.py
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, ".")
from preprocessing.visualization import plot_comparison_panel

RESULTS = Path("results")
DATA = Path("data")


def grid_axes(preds: np.ndarray):
    return np.sort(np.unique(preds[:, 0])), np.sort(np.unique(preds[:, 1]))


def add_quadratic_trend(preds: np.ndarray, coeffs_path: Path) -> np.ndarray:
    """Return prediction values with the detrending trend surface added back."""
    c = np.loadtxt(coeffs_path)
    x, y = preds[:, 0], preds[:, 1]
    trend = c[0] + c[1] * x + c[2] * y + c[3] * x ** 2 + c[4] * y ** 2 + c[5] * x * y
    return preds[:, 2] + trend


def panel(x_grid, y_grid, pred_vals, var_vals, train_locs, train_vals, out):
    plot_comparison_panel(
        x_grid=x_grid, y_grid=y_grid,
        predictions=pred_vals, variances=var_vals,
        train_locs=train_locs, train_vals=train_vals,
        output_path=out, basemap=False, boundary=True,
    )
    print(f"wrote {out} (+ .svg)")


def main():
    data_05 = np.loadtxt(DATA / "delta_0.05.csv", delimiter=",")
    data_02 = np.loadtxt(DATA / "delta_0.02.csv", delimiter=",")
    data_bin = np.loadtxt(DATA / "binary_sample_5401.csv", delimiter=",")

    # Fig 5.6 - Universal Kriging (detrended): residual field + quadratic trend
    det = np.loadtxt(RESULTS / "predictions_rs_detrended.csv", delimiter=",")
    det_final = add_quadratic_trend(det, DATA / "trend_coeffs_delta_0.05.csv")
    xg, yg = grid_axes(det)
    panel(xg, yg, det_final, det[:, 3], data_05[:, :2], data_05[:, 2],
          RESULTS / "painel_comparativo_detrended.png")

    # Fig 5.7 - Indicator Kriging (observation panel uses the raw binary sample)
    ind = np.loadtxt(RESULTS / "predictions_rs_indicator.csv", delimiter=",")
    xg, yg = grid_axes(ind)
    panel(xg, yg, ind[:, 2], ind[:, 3], data_bin[:, :2], data_bin[:, 2],
          RESULTS / "painel_comparativo_indicator.png")

    # Fig 5.9 - native Kriging at delta=0.02
    d02 = np.loadtxt(RESULTS / "predictions_rs_delta002.csv", delimiter=",")
    xg, yg = grid_axes(d02)
    panel(xg, yg, d02[:, 2], d02[:, 3], data_02[:, :2], data_02[:, 2],
          RESULTS / "painel_comparativo_delta002.png")


if __name__ == "__main__":
    main()
