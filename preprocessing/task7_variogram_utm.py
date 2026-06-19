"""UTM/km empirical variogram for the canonical Haldane-logit field."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, ".")
from preprocessing.kriging import MaternParams, matern_covariance


DEFAULT_THETA = MaternParams(6.34485611, 19.18492718, 0.54733473, 0.000001)


def parse_theta(raw: str) -> MaternParams:
    vals = [float(v) for v in raw.split(":")]
    if len(vals) != 4:
        raise argparse.ArgumentTypeError("theta must be sigma2:beta:nu:nugget")
    return MaternParams(vals[0], vals[1], vals[2], vals[3])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=Path("data/delta_0.05_logit_utm.csv"))
    parser.add_argument("--theta", type=parse_theta, default=DEFAULT_THETA)
    parser.add_argument("--sample", type=int, default=2500)
    parser.add_argument("--maxh", type=float, default=300.0)
    parser.add_argument(
        "--output", type=Path, default=Path("results/variogram_utm_logit.png")
    )
    return parser.parse_args()


def load(path: Path) -> tuple[np.ndarray, np.ndarray]:
    arr = np.genfromtxt(path, delimiter=",")
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr[:, :2], arr[:, 2]


def binned(
    h: np.ndarray, gamma: np.ndarray, bins: np.ndarray, mask: np.ndarray
) -> np.ndarray:
    centers = 0.5 * (bins[:-1] + bins[1:])
    out = np.full(len(centers), np.nan)
    for i in range(len(centers)):
        m = mask & (h >= bins[i]) & (h < bins[i + 1])
        if int(m.sum()) > 30:
            out[i] = float(gamma[m].mean())
    return out


def main() -> None:
    args = parse_args()
    theta = args.theta
    xy, z = load(args.csv)
    rng = np.random.default_rng(42)
    idx = rng.choice(len(xy), size=min(args.sample, len(xy)), replace=False)
    xy, z = xy[idx], z[idx]

    dx = xy[:, 0][:, None] - xy[:, 0][None, :]
    dy = xy[:, 1][:, None] - xy[:, 1][None, :]
    h = np.sqrt(dx**2 + dy**2)
    semi = 0.5 * (z[:, None] - z[None, :]) ** 2
    ang = np.degrees(np.arctan2(dy, dx)) % 180.0

    iu = np.triu_indices(len(z), k=1)
    h, semi, ang = h[iu], semi[iu], ang[iu]

    bins = np.linspace(0.0, args.maxh, 25)
    centers = 0.5 * (bins[:-1] + bins[1:])
    omni = binned(h, semi, bins, np.ones_like(h, dtype=bool))
    dirs = {
        "0 deg (E-W)": (ang < 22.5) | (ang >= 157.5),
        "45 deg": (ang >= 22.5) & (ang < 67.5),
        "90 deg (N-S)": (ang >= 67.5) & (ang < 112.5),
        "135 deg": (ang >= 112.5) & (ang < 157.5),
    }
    dir_vals = {name: binned(h, semi, bins, mask) for name, mask in dirs.items()}

    hh = np.linspace(1e-3, args.maxh, 400)
    model = (theta.sigma2 + theta.nugget) - matern_covariance(hh, theta)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    axes[0].plot(centers, omni, "o", color="#4477aa", label="empirical")
    axes[0].plot(hh, model, "-", color="#cc6677", label="canonical Matérn")
    axes[0].axhline(theta.sigma2, color="0.35", linestyle=":", label=f"sigma2={theta.sigma2:.3f}")
    axes[0].set(
        title="Omnidirectional Variogram (UTM logit)",
        xlabel="Distance h (km)",
        ylabel="Semivariance",
    )
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    for name, vals in dir_vals.items():
        axes[1].plot(centers, vals, "o-", label=name, alpha=0.85)
    axes[1].set(
        title="Directional Variograms (UTM logit)",
        xlabel="Distance h (km)",
        ylabel="Semivariance",
    )
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.output, dpi=150)
    fig.savefig(args.output.with_suffix(".svg"), format="svg")
    plt.close(fig)

    print("=== Task 7 UTM logit variogram ===")
    print(f"csv={args.csv}")
    print(f"sample={len(z)} pairs={len(h)} maxh={args.maxh:.1f} km")
    print(f"data var={z.var():.6f}")
    print(f"empirical omni max={np.nanmax(omni):.6f}")
    print(
        "theta="
        f"({theta.sigma2:.8f},{theta.beta:.8f},{theta.nu:.8f},{theta.nugget:.8f})"
    )
    print("directional max semivariance:")
    for name, vals in dir_vals.items():
        print(f"  {name}: {np.nanmax(vals):.6f}")
    finite_dir_max = [np.nanmax(vals) for vals in dir_vals.values() if np.isfinite(vals).any()]
    print(f"directional max/min ratio={max(finite_dir_max) / min(finite_dir_max):.3f}")
    print(f"saved {args.output}")
    print(f"saved {args.output.with_suffix('.svg')}")
    print("DONE")


if __name__ == "__main__":
    main()
