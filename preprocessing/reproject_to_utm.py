"""Run #1 (spine of the maximal plan): reproject coordinates from lon/lat degrees
to a metric CRS so distances are isotropic and correct on both axes.

EPSG:4326 (WGS84 lon/lat) -> EPSG:31982 (SIRGAS 2000 / UTM 22S), output in
KILOMETRES (so beta lands in the hundreds, nicer conditioning than metres).

Rewrites every consumer-facing CSV in projected coords with a `_utm` suffix so the
rest of the pipeline (MLE, R prediction, kriging.py, IDW) automatically sees metric
distances. The cell SET is unchanged; only the (x, y) columns are transformed.

Usage: .venv/bin/python3 preprocessing/reproject_to_utm.py
"""
import csv
from pathlib import Path
from pyproj import Transformer

# always_xy=True => input/output ordered (x=lon/easting, y=lat/northing)
TF = Transformer.from_crs("EPSG:4326", "EPSG:31982", always_xy=True)

ROOT = Path(".")
FOLDS = ROOT / "preprocessing/output/validate_cv_folds"
FOLDS_UTM = ROOT / "preprocessing/output/validate_cv_folds_utm"

# (input, output) CSV pairs. No header: lon, lat, measurement.
TARGETS = [
    (ROOT / "data/delta_0.05.csv", ROOT / "data/delta_0.05_utm.csv"),
    (ROOT / "data/delta_0.02.csv", ROOT / "data/delta_0.02_utm.csv"),
]
for k in range(1, 9):
    for kind in ("train", "test"):
        TARGETS.append(
            (FOLDS / f"fold_{k:02d}_{kind}.csv",
             FOLDS_UTM / f"fold_{k:02d}_{kind}.csv")
        )


def reproject_csv(src: Path, dst: Path):
    lons, lats, meas = [], [], []
    with open(src) as f:
        for row in csv.reader(f):
            if not row:
                continue
            lons.append(float(row[0]))
            lats.append(float(row[1]))
            meas.append(row[2])  # keep as string, preserve precision
    ex, ny = TF.transform(lons, lats)  # metres
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", newline="") as f:
        w = csv.writer(f)
        for x_m, y_m, m in zip(ex, ny, meas):
            w.writerow([f"{x_m / 1000.0:.6f}", f"{y_m / 1000.0:.6f}", m])  # km
    return len(meas)


if __name__ == "__main__":
    for src, dst in TARGETS:
        if not src.exists():
            print(f"SKIP (missing): {src}")
            continue
        n = reproject_csv(src, dst)
        print(f"{src}  ->  {dst}  ({n} rows, km / UTM 22S)")
    print("DONE. Re-run all downstream steps on the *_utm.csv files.")
    print("Sanity: a degree of lon ~96 km and lat ~111 km at 30.5S are now equal "
          "metric units; beta will read in km (domain ~750 km).")
