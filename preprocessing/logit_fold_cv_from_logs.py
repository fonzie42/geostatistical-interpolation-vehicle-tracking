"""Score Haldane-logit CV with per-fold ExaGeoStat MLE theta logs."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
from scipy.special import expit

sys.path.insert(0, ".")
from preprocessing.kriging import MaternParams
from preprocessing.logit_cv_utm_fast import (
    NOMINAL_Z,
    krige_centered,
    load,
    load_truth,
    parse_theta,
)


THETA_RE = re.compile(
    r"#Found Maximum Theta at:\s+"
    r"([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)"
)
ITER_RE = re.compile(r"#Number of MLE Iterations:\s+([0-9]+)")
LOGLIK_RE = re.compile(r"#Final Log Likelihood value:\s+([0-9.eE+-]+)")


def parse_log(path: Path) -> tuple[MaternParams, int | None, float | None]:
    text = path.read_text()
    theta_match = THETA_RE.search(text)
    if theta_match is None:
        raise RuntimeError(f"{path}: no final theta found")
    theta = MaternParams(*(float(theta_match.group(i)) for i in range(1, 5)))

    iter_match = ITER_RE.search(text)
    loglik_match = LOGLIK_RE.search(text)
    iterations = int(iter_match.group(1)) if iter_match else None
    loglik = float(loglik_match.group(1)) if loglik_match else None
    return theta, iterations, loglik


def metrics(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float, float]:
    err = pred - truth
    return (
        float(np.sqrt(np.mean(err**2))),
        float(np.mean(np.abs(err))),
        float(np.mean(err)),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fold-dir",
        type=Path,
        default=Path("preprocessing/output/validate_cv_folds_logit_utm"),
    )
    parser.add_argument(
        "--log-template",
        default="logs/mle_logit_utm_fold{fold:02d}_gpu.log",
    )
    parser.add_argument(
        "--global-theta",
        type=parse_theta,
        default=parse_theta("6.34485611:19.18492718:0.54733473:0.000001"),
        help="Full-data canonical theta for comparison only",
    )
    return parser.parse_args()


def score_fold(
    fold_dir: Path,
    fold: int,
    theta: MaternParams,
) -> tuple[dict[str, float], dict[int, np.ndarray]]:
    train_locs, train_vals = load(fold_dir / f"fold_{fold:02d}_train.csv")
    test_locs, _test_logit = load(fold_dir / f"fold_{fold:02d}_test.csv")
    truth = load_truth(fold_dir / f"fold_{fold:02d}_test_truth.csv")

    pred_logit, var_logit, elapsed = krige_centered(
        train_locs, train_vals, test_locs, theta, 384, 256
    )
    pred_p = expit(pred_logit)
    rmse, mae, bias = metrics(pred_p, truth)

    sd = np.sqrt(var_logit)
    coverage_parts = {}
    coverages = {}
    for q, z in NOMINAL_Z.items():
        lo = expit(pred_logit - z * sd)
        hi = expit(pred_logit + z * sd)
        inside = (truth >= lo) & (truth <= hi)
        coverage_parts[int(q * 100)] = inside
        coverages[f"cov_{int(q * 100)}"] = float(np.mean(inside))

    row = {
        "n": len(truth),
        "rmse": rmse,
        "mae": mae,
        "bias": bias,
        "pred_min": float(pred_p.min()),
        "pred_max": float(pred_p.max()),
        "var_min": float(var_logit.min()),
        "var_max": float(var_logit.max()),
        "elapsed": elapsed,
        **coverages,
    }
    return row, coverage_parts


def main() -> None:
    args = parse_args()
    rows = []
    global_rows = []
    coverage_parts = {int(q * 100): [] for q in NOMINAL_Z}
    global_coverage_parts = {int(q * 100): [] for q in NOMINAL_Z}

    print("logit UTM per-fold-theta CV from ExaGeoStat MLE logs", flush=True)
    print(
        "global comparison theta="
        f"({args.global_theta.sigma2:.8f},{args.global_theta.beta:.8f},"
        f"{args.global_theta.nu:.8f},{args.global_theta.nugget:.8f})",
        flush=True,
    )

    for fold in range(1, 9):
        log_path = Path(args.log_template.format(fold=fold))
        theta, iterations, loglik = parse_log(log_path)
        row, cov_parts = score_fold(args.fold_dir, fold, theta)
        global_row, global_cov_parts = score_fold(args.fold_dir, fold, args.global_theta)

        rows.append(row)
        global_rows.append(global_row)
        for key, value in cov_parts.items():
            coverage_parts[key].append(value)
        for key, value in global_cov_parts.items():
            global_coverage_parts[key].append(value)

        print(
            f"  fold {fold:02d} N={row['n']:4.0f} "
            f"theta=({theta.sigma2:.6f},{theta.beta:.6f},"
            f"{theta.nu:.6f},{theta.nugget:.6f}) "
            f"iters={iterations if iterations is not None else 'NA'} "
            f"loglik={loglik if loglik is not None else 'NA'} "
            f"RMSE local={row['rmse']:.6f} global={global_row['rmse']:.6f} "
            f"MAE local={row['mae']:.6f} global={global_row['mae']:.6f}",
            flush=True,
        )

    def weighted(source: list[dict[str, float]], key: str) -> float:
        total = sum(row["n"] for row in source)
        return float(sum(row["n"] * row[key] for row in source) / total)

    total = int(sum(row["n"] for row in rows))
    print("\n=== weighted ===", flush=True)
    print(f"  N={total}", flush=True)
    for label, source, cov_source in (
        ("per-fold theta", rows, coverage_parts),
        ("global theta", global_rows, global_coverage_parts),
    ):
        print(
            f"  {label}: RMSE={weighted(source, 'rmse'):.6f} "
            f"MAE={weighted(source, 'mae'):.6f} "
            f"bias={weighted(source, 'bias'):+.6f}",
            flush=True,
        )
        print(
            f"    pred_range=[{min(row['pred_min'] for row in source):.6f},"
            f"{max(row['pred_max'] for row in source):.6f}] "
            f"var_range=[{min(row['var_min'] for row in source):.6f},"
            f"{max(row['var_max'] for row in source):.6f}]",
            flush=True,
        )
        for pct in sorted(cov_source):
            cov = float(np.mean(np.concatenate(cov_source[pct])))
            print(f"    cov{pct}={cov * 100:.2f}%", flush=True)

    delta = weighted(global_rows, "rmse") - weighted(rows, "rmse")
    print(
        f"  leakage delta: RMSE global-minus-local={delta:+.6f} "
        f"({delta / weighted(global_rows, 'rmse') * 100:+.2f}%)",
        flush=True,
    )


if __name__ == "__main__":
    main()
