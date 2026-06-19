"""Fast UTM Haldane-logit CV using an ExaGeoStat full-data theta.

This avoids eight R-interface runs. It uses the same Matérn covariance as the
project's Python kriging code, centers each training fold on its own logit mean,
predicts in logit space, then evaluates predictions and intervals after expit.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
from scipy.linalg import cho_factor, cho_solve
from scipy.special import expit
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


def load_truth(path: Path) -> np.ndarray:
    arr = np.genfromtxt(path, delimiter=",", names=True)
    return np.asarray(arr["proportion"], dtype=float)


def load_counts(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = np.genfromtxt(path, delimiter=",", names=True)
    locs = np.column_stack(
        [
            np.asarray(arr["x_utm_km"], dtype=float),
            np.asarray(arr["y_utm_km"], dtype=float),
        ]
    )
    hlogit = np.asarray(arr["hlogit"], dtype=float)
    truth = np.asarray(arr["proportion"], dtype=float)
    return locs, hlogit, truth


def block_ids(locs: np.ndarray, n_lat: int = 3, n_lon: int = 3) -> np.ndarray:
    x, y = locs[:, 0], locs[:, 1]
    x_edges = np.linspace(x.min(), x.max(), n_lon + 1)
    y_edges = np.linspace(y.min(), y.max(), n_lat + 1)
    x_block = np.clip(np.digitize(x, x_edges[1:-1]), 0, n_lon - 1)
    y_block = np.clip(np.digitize(y, y_edges[1:-1]), 0, n_lat - 1)
    return y_block * n_lon + x_block


def build_covariance_blocked(
    locs: np.ndarray,
    theta: MaternParams,
    block_size: int,
) -> np.ndarray:
    n = len(locs)
    cov = np.empty((n, n), dtype=np.float64)
    x = locs[:, 0]
    y = locs[:, 1]

    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        d = np.hypot(x[start:end, None] - x[None, :], y[start:end, None] - y[None, :])
        cov[start:end, :] = matern_covariance(d, theta)

    cov[np.diag_indices_from(cov)] = theta.sigma2 + theta.nugget
    return cov


def cross_covariance_block(
    train_locs: np.ndarray,
    test_locs: np.ndarray,
    theta: MaternParams,
) -> np.ndarray:
    d_cross = cdist(train_locs, test_locs)
    return matern_covariance(d_cross, theta)


def krige_centered(
    train_locs: np.ndarray,
    train_vals: np.ndarray,
    test_locs: np.ndarray,
    theta: MaternParams,
    cov_block_size: int,
    pred_batch_size: int,
) -> tuple[np.ndarray, np.ndarray, float]:
    t0 = time.monotonic()
    mean = train_vals.mean()
    y = train_vals - mean

    c_train = build_covariance_blocked(train_locs, theta, cov_block_size)
    cf = cho_factor(c_train, lower=True, check_finite=False, overwrite_a=True)

    pred = np.empty(len(test_locs), dtype=np.float64)
    var = np.empty(len(test_locs), dtype=np.float64)
    sill = theta.sigma2 + theta.nugget

    for start in range(0, len(test_locs), pred_batch_size):
        end = min(start + pred_batch_size, len(test_locs))
        c_cross = cross_covariance_block(train_locs, test_locs[start:end], theta)
        weights = cho_solve(cf, c_cross, check_finite=False)
        pred[start:end] = weights.T @ y + mean
        var[start:end] = sill - np.einsum("ij,ij->j", c_cross, weights)

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
        default=parse_theta("6.34485611:19.18492718:0.54733473:0.000001"),
        help="ExaGeoStat theta as sigma2:beta:nu:nugget",
    )
    parser.add_argument(
        "--mode",
        choices=("folds", "blocks"),
        default="folds",
        help="folds uses existing fold CSVs; blocks uses 3x3 spatial blocks",
    )
    parser.add_argument(
        "--fold-dir",
        type=Path,
        default=Path("preprocessing/output/validate_cv_folds_logit_utm"),
    )
    parser.add_argument(
        "--counts-csv",
        type=Path,
        default=Path("preprocessing/output/logit_counts_delta_0.02_utm.csv"),
    )
    parser.add_argument("--cov-block-size", type=int, default=384)
    parser.add_argument("--pred-batch-size", type=int, default=256)
    return parser.parse_args()


def iter_folds(args: argparse.Namespace):
    for fold in range(1, 9):
        train_locs, train_vals = load(args.fold_dir / f"fold_{fold:02d}_train.csv")
        test_locs, _test_logit = load(args.fold_dir / f"fold_{fold:02d}_test.csv")
        truth = load_truth(args.fold_dir / f"fold_{fold:02d}_test_truth.csv")
        yield f"fold {fold:02d}", train_locs, train_vals, test_locs, truth


def iter_blocks(args: argparse.Namespace):
    locs, vals, truth = load_counts(args.counts_csv)
    bid = block_ids(locs)
    for block in sorted(set(bid.tolist())):
        test = bid == block
        yield (
            f"block {block:02d}",
            locs[~test],
            vals[~test],
            locs[test],
            truth[test],
        )


def main() -> None:
    args = parse_args()
    theta = args.theta
    rows = []
    coverage_parts = {q: [] for q in NOMINAL_Z}

    print(
        f"logit UTM fast CV mode={args.mode}; theta="
        f"({theta.sigma2:.8f},{theta.beta:.8f},{theta.nu:.8f},{theta.nugget:.8f})",
        flush=True,
    )

    iterator = iter_folds(args) if args.mode == "folds" else iter_blocks(args)
    for label, train_locs, train_vals, test_locs, truth in iterator:
        pred_logit, var_logit, elapsed = krige_centered(
            train_locs,
            train_vals,
            test_locs,
            theta,
            args.cov_block_size,
            args.pred_batch_size,
        )
        pred_p = expit(pred_logit)
        rmse, mae, bias = metrics(pred_p, truth)

        sd = np.sqrt(var_logit)
        cov = {}
        for q, z in NOMINAL_Z.items():
            lo = expit(pred_logit - z * sd)
            hi = expit(pred_logit + z * sd)
            inside = (truth >= lo) & (truth <= hi)
            cov[q] = float(np.mean(inside))
            coverage_parts[q].append(inside)

        row = {
            "label": label,
            "n": len(truth),
            "rmse": rmse,
            "mae": mae,
            "bias": bias,
            "pred_min": float(pred_p.min()),
            "pred_max": float(pred_p.max()),
            "var_min": float(var_logit.min()),
            "var_max": float(var_logit.max()),
            "elapsed": elapsed,
            **{f"cov_{int(q * 100)}": cov[q] for q in NOMINAL_Z},
        }
        rows.append(row)
        print(
            f"  {label} N={row['n']:5d} "
            f"RMSE={rmse:.6f} MAE={mae:.6f} bias={bias:+.6f} "
            f"cov95={cov[0.95] * 100:.1f}% "
            f"p=[{row['pred_min']:.6f},{row['pred_max']:.6f}] "
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
    print(
        f"  total_time={sum(row['elapsed'] for row in rows):.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
