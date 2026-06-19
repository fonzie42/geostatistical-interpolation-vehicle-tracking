"""Prepare count-based Haldane-logit inputs in UTM coordinates.

This is the canonical ExaGeoStatCPP input for the thesis revision's primary
model. It re-aggregates the raw parquet so each spatial cell keeps its binomial
counts, then writes:

  - data/delta_<delta>_logit_utm.csv: x_km,y_km,hlogit without header
  - preprocessing/output/logit_counts_delta_<delta>_utm.csv: audited metadata

The measurement is the empirical Haldane logit:

    log((k + 0.5) / (n - k + 0.5))

where n is the per-cell event count and k is the clamped online count. This is
the count-based transform that avoids the p=0/1 blow-up of epsilon clamping.
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
from pyproj import Transformer

sys.path.insert(0, ".")
from preprocessing.config import PipelineConfig


ROOT = Path(".")
OUT_COUNTS = ROOT / "preprocessing/output"
FOLDS = OUT_COUNTS / "validate_cv_folds"
FOLDS_LOGIT_UTM = OUT_COUNTS / "validate_cv_folds_logit_utm"
TF = Transformer.from_crs("EPSG:4326", "EPSG:31982", always_xy=True)


def _delta_tag(delta: float) -> str:
    return f"{delta:.2f}"


def aggregate_counts(delta: float) -> pl.DataFrame:
    cfg = PipelineConfig(delta=delta)

    lf = (
        pl.scan_parquet(cfg.input_path)
        .filter(
            pl.col("latitude").is_not_null()
            & pl.col("longitude").is_not_null()
            & pl.col("online").is_not_null()
            & (pl.col("latitude") >= cfg.lat_min)
            & (pl.col("latitude") <= cfg.lat_max)
            & (pl.col("longitude") >= cfg.lon_min)
            & (pl.col("longitude") <= cfg.lon_max)
        )
        .with_columns(
            pl.when(pl.col("online") > cfg.online_max)
            .then(cfg.online_max)
            .otherwise(pl.col("online"))
            .alias("online")
        )
        .with_columns(
            ((pl.col("latitude") - cfg.lat_min) / cfg.delta)
            .floor()
            .cast(pl.Int32)
            .alias("cell_lat_idx"),
            ((pl.col("longitude") - cfg.lon_min) / cfg.delta)
            .floor()
            .cast(pl.Int32)
            .alias("cell_lon_idx"),
        )
        .group_by("cell_lat_idx", "cell_lon_idx")
        .agg(
            pl.col("online").count().alias("n_events"),
            pl.col("online").sum().alias("n_online"),
        )
        .filter(pl.col("n_events") >= cfg.min_events)
        .with_columns(
            (cfg.lon_min + (pl.col("cell_lon_idx") + 0.5) * cfg.delta).alias("lon"),
            (cfg.lat_min + (pl.col("cell_lat_idx") + 0.5) * cfg.delta).alias("lat"),
        )
        .with_columns(
            (pl.col("n_online") / pl.col("n_events")).alias("proportion"),
            (
                (
                    (pl.col("n_online") + 0.5)
                    / (pl.col("n_events") - pl.col("n_online") + 0.5)
                )
                .log()
            ).alias("hlogit"),
        )
        .sort("cell_lat_idx", "cell_lon_idx")
    )

    df = lf.collect()
    x_m, y_m = TF.transform(df["lon"].to_list(), df["lat"].to_list())
    return df.with_columns(
        pl.Series("x_utm_km", [x / 1000.0 for x in x_m]),
        pl.Series("y_utm_km", [y / 1000.0 for y in y_m]),
    )


def write_outputs(df: pl.DataFrame, delta: float) -> tuple[Path, Path]:
    tag = _delta_tag(delta)
    exa_path = ROOT / f"data/delta_{tag}_logit_utm.csv"
    counts_path = OUT_COUNTS / f"logit_counts_delta_{tag}_utm.csv"

    exa_path.parent.mkdir(parents=True, exist_ok=True)
    counts_path.parent.mkdir(parents=True, exist_ok=True)

    df.select("x_utm_km", "y_utm_km", "hlogit").write_csv(
        exa_path, include_header=False
    )
    df.select(
        "cell_lat_idx",
        "cell_lon_idx",
        "lon",
        "lat",
        "x_utm_km",
        "y_utm_km",
        "n_events",
        "n_online",
        "proportion",
        "hlogit",
    ).write_csv(counts_path)

    return exa_path, counts_path


def _coord_key(lon: float, lat: float) -> tuple[float, float]:
    return (round(lon, 10), round(lat, 10))


def write_delta005_folds(df: pl.DataFrame) -> None:
    """Write Haldane-logit UTM folds matching the existing delta=0.05 split."""
    lookup = {
        _coord_key(row["lon"], row["lat"]): row
        for row in df.to_dicts()
    }

    FOLDS_LOGIT_UTM.mkdir(parents=True, exist_ok=True)
    for fold in range(1, 9):
        for kind in ("train", "test"):
            src = FOLDS / f"fold_{fold:02d}_{kind}.csv"
            out = FOLDS_LOGIT_UTM / f"fold_{fold:02d}_{kind}.csv"
            truth = FOLDS_LOGIT_UTM / f"fold_{fold:02d}_{kind}_truth.csv"
            if not src.exists():
                print(f"  SKIP missing fold input: {src}")
                continue

            fold_df = pl.read_csv(
                src,
                has_header=False,
                new_columns=["lon", "lat", "proportion_native"],
            )
            rows = []
            missing = []
            for row in fold_df.to_dicts():
                key = _coord_key(row["lon"], row["lat"])
                matched = lookup.get(key)
                if matched is None:
                    missing.append(key)
                    continue
                rows.append(matched)

            if missing:
                raise RuntimeError(
                    f"{src}: {len(missing)} fold coordinates did not match counts"
                )

            out_df = pl.DataFrame(rows)
            out_df.select("x_utm_km", "y_utm_km", "hlogit").write_csv(
                out, include_header=False
            )
            out_df.select(
                "lon",
                "lat",
                "x_utm_km",
                "y_utm_km",
                "n_events",
                "n_online",
                "proportion",
                "hlogit",
            ).write_csv(truth)
            print(f"  fold {fold:02d} {kind}: {out_df.height} rows -> {out}")


def main() -> None:
    for delta in (0.05, 0.02):
        df = aggregate_counts(delta)
        exa_path, counts_path = write_outputs(df, delta)
        print(
            f"delta={delta:.2f} rows={df.height} "
            f"p=[{df['proportion'].min():.6f},{df['proportion'].max():.6f}] "
            f"hlogit_mean={df['hlogit'].mean():.6f} "
            f"hlogit_var={df['hlogit'].var():.6f}"
        )
        print(f"  ExaGeoStat: {exa_path}")
        print(f"  counts:     {counts_path}")
        if delta == 0.05:
            write_delta005_folds(df)


if __name__ == "__main__":
    main()
