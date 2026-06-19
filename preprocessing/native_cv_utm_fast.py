"""Fast native-scale UTM Kriging CV using ExaGeoStat full-data theta.

This mirrors ``logit_cv_utm_fast.py`` but evaluates the native proportion scale
directly. It is intended for provenance checks after the canonical C++ MLE logs
have produced theta values.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.spatial.distance import cdist

sys.path.insert(0, ".")
from preprocessing.kriging import MaternParams, matern_covariance


NOMINAL_Z = {
    0.50: 0.6744897501960817,
    0.80: 1.2815515655446004,
    0.90: 1.6448536269514722,
    0.95: 1.959963984540054,
}


def load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    arr = np.genfromtxt(path, delimiter=",")
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr[:, :2], arr[:, 2]


def block_ids(locs: np.ndarray, n_lat: int = 3, n_lon: int = 3) -> np.ndarray:
    x, y = locs[:, 0], locs[:, 1]
    x_edges = np.linspace(x.min(), x.max(), n_lon + 1)
    y_edges = np.linspace(y.min(), y.max(), n_lat + 1)
    x_block = np.clip(np.digitize(x, x_edges[1:-1]), 0, n_lon - 1)
    y_block = np.clip(np.digitize(y, y_edges[1:-1]), 0, n_lat - 1)
    return y_block * n_lon + x_block


def krige_centered(
    train_locs: np.ndarray,
    train_vals: np.ndarray,
    test_locs: np.ndarray,
    theta: MaternParams,
) -> tuple[np.ndarray, np.ndarray, float]:
    t0 = time.monotonic()
    mean = train_vals.mean()
    y = train_vals - mean

    d_train = cdist(train_locs, train_locs)
    c_train = matern_covariance(d_train, theta)
    c_train[np.diag_indices_from(c_train)] = theta.sigma2 + theta.nugget
    cf = cho_factor(c_train, lower=True, check_finite=False)

    d_cross = cdist(train_locs, test_locs)
    c_cross = matern_covariance(d_cross, theta)
    weights = cho_solve(cf, c_cross, check_finite=False)

    pred = weights.T @ y + mean
    var = (theta.sigma2 + theta.nugget) - np.einsum("ij,ij->j", c_cross, weights)
    return pred, np.maximum(var, 0.0), time.monotonic() - t0


def metrics(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float, float]:
    err = pred - truth
    return (
        float(np.sqrt(np.mean(err**2))),
        float(np.mean(np.abs(err))),
        float(np.mean(err)),
    )


def parse_theta(raw: str) -> MaternParams:
    parts = [float(x) for x in raw.split(":")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("theta must be sigma2:beta:nu:nugget")
    return MaternParams(parts[0], parts[1], parts[2], parts[3])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--theta",
        type=parse_theta,
        required=True,
        help="ExaGeoStat theta as sigma2:beta:nu:nugget",
    )
    parser.add_argument(
        "--mode",
        choices=("folds", "blocks"),
        required=True,
        help="folds uses existing delta=0.05 fold CSVs; blocks uses 3x3 blocks",
    )
    parser.add_argument(
        "--fold-dir",
        type=Path,
        default=Path("preprocessing/output/validate_cv_folds_utm"),
    )
    parser.add_argument(
        "--data-csv",
        type=Path,
        default=Path("data/delta_0.02_utm.csv"),
    )
    return parser.parse_args()


def iter_folds(args: argparse.Namespace):
    for fold in range(1, 9):
        train_locs, train_vals = load(args.fold_dir / f"fold_{fold:02d}_train.csv")
        test_locs, truth = load(args.fold_dir / f"fold_{fold:02d}_test.csv")
        yield f"fold {fold:02d}", train_locs, train_vals, test_locs, truth


def iter_blocks(args: argparse.Namespace):
    locs, vals = load(args.data_csv)
    bid = block_ids(locs)
    for block in sorted(set(bid.tolist())):
        test = bid == block
        yield (
            f"block {block:02d}",
            locs[~test],
            vals[~test],
            locs[test],
            vals[test],
        )


def main() -> None:
    args = parse_args()
    theta = args.theta
    rows = []
    coverage_parts = {q: [] for q in NOMINAL_Z}

    print(
        f"native UTM fast CV mode={args.mode}; theta="
        f"({theta.sigma2:.8f},{theta.beta:.8f},{theta.nu:.8f},{theta.nugget:.8f})",
        flush=True,
    )

    iterator = iter_folds(args) if args.mode == "folds" else iter_blocks(args)
    for label, train_locs, train_vals, test_locs, truth in iterator:
        pred, var, elapsed = krige_centered(train_locs, train_vals, test_locs, theta)
        rmse, mae, bias = metrics(pred, truth)

        sd = np.sqrt(var)
        cov = {}
        for q, z in NOMINAL_Z.items():
            lo = pred - z * sd
            hi = pred + z * sd
            inside = (truth >= lo) & (truth <= hi)
            cov[q] = float(np.mean(inside))
            coverage_parts[q].append(inside)

        row = {
            "label": label,
            "n": len(truth),
            "rmse": rmse,
            "mae": mae,
            "bias": bias,
            "pred_min": float(pred.min()),
            "pred_max": float(pred.max()),
            "var_min": float(var.min()),
            "var_max": float(var.max()),
            "elapsed": elapsed,
            **{f"cov_{int(q * 100)}": cov[q] for q in NOMINAL_Z},
        }
        rows.append(row)
        print(
            f"  {label} N={row['n']:5d} "
            f"RMSE={rmse:.6f} MAE={mae:.6f} bias={bias:+.6f} "
            f"cov95={cov[0.95] * 100:.1f}% "
            f"pred=[{row['pred_min']:.6f},{row['pred_max']:.6f}] "
            f"time={elapsed:.1f}s",
            flush=True,
        )

    total = sum(row["n"] for row in rows)

    def weighted(key: str) -> float:
        return sum(row["n"] * row[key] for row in rows) / total

    print("\n=== weighted ===", flush=True)
    print(f"  N={total}", flush=True)
    print(f"  RMSE={weighted('rmse'):.6f}", flush=True)
    print(f"  MAE={weighted('mae'):.6f}", flush=True)
    print(f"  bias={weighted('bias'):+.6f}", flush=True)
    print(
        f"  pred_range=[{min(row['pred_min'] for row in rows):.6f},"
        f"{max(row['pred_max'] for row in rows):.6f}]",
        flush=True,
    )
    print(
        f"  var_range=[{min(row['var_min'] for row in rows):.6f},"
        f"{max(row['var_max'] for row in rows):.6f}]",
        flush=True,
    )
    for q in NOMINAL_Z:
        cov = float(np.mean(np.concatenate(coverage_parts[q])))
        print(f"  cov{int(q * 100)}={cov * 100:.2f}%", flush=True)
    print(f"  total_time={sum(row['elapsed'] for row in rows):.1f}s", flush=True)


if __name__ == "__main__":
    main()
