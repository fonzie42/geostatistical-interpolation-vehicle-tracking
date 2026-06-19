"""Fast mean-only and IDW baselines on UTM folds and block splits."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist


FOLD_DIR = Path("preprocessing/output/validate_cv_folds_utm")


def load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    arr = np.genfromtxt(path, delimiter=",")
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr[:, :2], arr[:, 2]


def idw_predict(
    train_locs: np.ndarray,
    train_vals: np.ndarray,
    test_locs: np.ndarray,
    power: float = 2.0,
    batch_size: int = 512,
) -> np.ndarray:
    out = np.empty(len(test_locs), dtype=float)
    for start in range(0, len(test_locs), batch_size):
        end = min(start + batch_size, len(test_locs))
        d = cdist(test_locs[start:end], train_locs)
        for j, dist in enumerate(d):
            zero = dist == 0
            if np.any(zero):
                out[start + j] = train_vals[zero].mean()
            else:
                w = 1.0 / np.power(dist, power)
                out[start + j] = np.dot(w, train_vals) / w.sum()
    return out


def metrics(pred: np.ndarray, true: np.ndarray) -> tuple[float, float, float]:
    err = pred - true
    return (
        float(np.sqrt(np.mean(err**2))),
        float(np.mean(np.abs(err))),
        float(np.mean(err)),
    )


def block_ids(locs: np.ndarray, n_lat: int = 3, n_lon: int = 3) -> np.ndarray:
    x, y = locs[:, 0], locs[:, 1]
    x_edges = np.linspace(x.min(), x.max(), n_lon + 1)
    y_edges = np.linspace(y.min(), y.max(), n_lat + 1)
    x_block = np.clip(np.digitize(x, x_edges[1:-1]), 0, n_lon - 1)
    y_block = np.clip(np.digitize(y, y_edges[1:-1]), 0, n_lat - 1)
    return y_block * n_lon + x_block


def print_weighted(rows: list[tuple[int, tuple[float, float, float], tuple[float, float, float]]]) -> None:
    total = sum(row[0] for row in rows)

    def weighted(method_idx: int, metric_idx: int) -> float:
        return sum(row[0] * row[method_idx][metric_idx] for row in rows) / total

    print("\n=== weighted ===", flush=True)
    print(f"  N={total}", flush=True)
    print(
        f"  Mean-only: RMSE={weighted(1, 0):.6f} "
        f"MAE={weighted(1, 1):.6f} bias={weighted(1, 2):+.6f}",
        flush=True,
    )
    print(
        f"  IDW:       RMSE={weighted(2, 0):.6f} "
        f"MAE={weighted(2, 1):.6f} bias={weighted(2, 2):+.6f}",
        flush=True,
    )


def run_delta005_folds() -> None:
    rows = []
    print(f"UTM baselines from {FOLD_DIR}", flush=True)
    for fold in range(1, 9):
        train_locs, train_vals = load(FOLD_DIR / f"fold_{fold:02d}_train.csv")
        test_locs, test_vals = load(FOLD_DIR / f"fold_{fold:02d}_test.csv")
        mean_pred = np.full(len(test_vals), train_vals.mean())
        idw_pred = idw_predict(train_locs, train_vals, test_locs)
        mean_metrics = metrics(mean_pred, test_vals)
        idw_metrics = metrics(idw_pred, test_vals)
        rows.append((len(test_vals), mean_metrics, idw_metrics))
        print(
            f"  fold {fold:02d} N={len(test_vals):4d} "
            f"mean RMSE={mean_metrics[0]:.6f} MAE={mean_metrics[1]:.6f} "
            f"IDW RMSE={idw_metrics[0]:.6f} MAE={idw_metrics[1]:.6f}",
            flush=True,
        )

    print_weighted(rows)


def run_blocks(csv_path: Path, label: str) -> None:
    locs, vals = load(csv_path)
    bid = block_ids(locs)
    rows = []
    print(f"\nUTM baselines for {csv_path} ({label}; 3x3 spatial blocks)", flush=True)
    for block in sorted(set(bid.tolist())):
        test = bid == block
        train_locs, train_vals = locs[~test], vals[~test]
        test_locs, test_vals = locs[test], vals[test]
        mean_pred = np.full(len(test_vals), train_vals.mean())
        idw_pred = idw_predict(train_locs, train_vals, test_locs)
        mean_metrics = metrics(mean_pred, test_vals)
        idw_metrics = metrics(idw_pred, test_vals)
        rows.append((len(test_vals), mean_metrics, idw_metrics))
        print(
            f"  block {block:02d} N={len(test_vals):5d} "
            f"mean RMSE={mean_metrics[0]:.6f} MAE={mean_metrics[1]:.6f} "
            f"IDW RMSE={idw_metrics[0]:.6f} MAE={idw_metrics[1]:.6f}",
            flush=True,
        )
    print_weighted(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-folds",
        action="store_true",
        help="Do not rerun the fixed delta=0.05 fold baselines.",
    )
    parser.add_argument(
        "--block-csv",
        action="append",
        type=Path,
        default=None,
        help="UTM CSV to score with 3x3 spatial blocks; repeatable.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_folds:
        run_delta005_folds()
    block_csvs = args.block_csv or [Path("data/delta_0.02_utm.csv")]
    for csv_path in block_csvs:
        run_blocks(csv_path, csv_path.stem)


if __name__ == "__main__":
    main()
