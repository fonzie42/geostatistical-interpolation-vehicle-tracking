"""Regenerate Figure 4.1: the observed cell-proportion map
(mapa_observacoes_boundary.png).

Loads the aggregated delta=0.05 connectivity proportions and draws them as a
scatter colored by proportion, with the Rio Grande do Sul state boundary and no
basemap, matching the thesis figure. Uses
preprocessing.visualization.plot_observed_data.

Run from repo root:  python preprocessing/generate_observations_map.py
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, ".")
from preprocessing.visualization import plot_observed_data

DATA = Path("data")
RESULTS = Path("results")


def main():
    data = np.loadtxt(DATA / "delta_0.05.csv", delimiter=",")  # columns: x, y, proportion
    out = RESULTS / "mapa_observacoes_boundary.png"
    plot_observed_data(
        locs=data[:, :2], values=data[:, 2],
        output_path=out, basemap=False, boundary=True,
    )
    print(f"wrote {out} (+ .svg)")


if __name__ == "__main__":
    main()
