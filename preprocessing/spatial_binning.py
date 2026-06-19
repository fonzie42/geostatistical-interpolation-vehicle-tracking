"""Spatial binning and aggregation of binary GPS connectivity observations."""

import numpy as np
import polars as pl

from preprocessing.config import PipelineConfig


class SpatialBinner:
    """Aggregates raw binary (online/offline) GPS points into spatial grid cells,
    computing per-cell connectivity proportions."""

    def __init__(self, config: PipelineConfig):
        self.config = config

    def load_and_filter(self) -> pl.LazyFrame:
        """Load Parquet data and filter invalid points.

        Filters applied:
          1. Remove points outside RS bounding box.
          2. Clamp online values > 1 to 1 (data artifacts).
          3. Remove rows with null values.
        """
        cfg = self.config
        lf = pl.scan_parquet(cfg.input_path)

        lf = lf.filter(
            pl.col("latitude").is_not_null()
            & pl.col("longitude").is_not_null()
            & pl.col("online").is_not_null()
            & (pl.col("latitude") >= cfg.lat_min)
            & (pl.col("latitude") <= cfg.lat_max)
            & (pl.col("longitude") >= cfg.lon_min)
            & (pl.col("longitude") <= cfg.lon_max)
        )

        # Clamp online > online_max to online_max (handles 2.0/3.0 artifacts)
        lf = lf.with_columns(
            pl.when(pl.col("online") > cfg.online_max)
            .then(cfg.online_max)
            .otherwise(pl.col("online"))
            .alias("online")
        )

        return lf

    def assign_cells(self, lf: pl.LazyFrame) -> pl.LazyFrame:
        """Assign each point to a grid cell based on delta.

        Cell indices are computed as floor((coord - min) / delta).
        Centroids are placed at the cell center: min + (index + 0.5) * delta.
        """
        cfg = self.config
        lf = lf.with_columns(
            ((pl.col("latitude") - cfg.lat_min) / cfg.delta)
            .floor()
            .cast(pl.Int32)
            .alias("cell_lat_idx"),
            ((pl.col("longitude") - cfg.lon_min) / cfg.delta)
            .floor()
            .cast(pl.Int32)
            .alias("cell_lon_idx"),
        )
        return lf

    def aggregate(self, lf: pl.LazyFrame) -> pl.DataFrame:
        """Aggregate points per cell: compute proportion, event count, uncertainty.

        Returns a DataFrame with columns:
          - cell_lat_idx, cell_lon_idx: grid indices
          - x_centroid, y_centroid: cell center coordinates (lon, lat)
          - n_events: total observations in cell
          - n_online: online observations in cell
          - proportion: n_online / n_events
          - std_dev: sqrt(p * (1-p) / n), binomial standard error
        """
        cfg = self.config

        df = (
            lf.group_by("cell_lat_idx", "cell_lon_idx")
            .agg(
                pl.col("online").count().alias("n_events"),
                pl.col("online").sum().alias("n_online"),
            )
            .filter(pl.col("n_events") >= cfg.min_events)
            .with_columns(
                (pl.col("n_online") / pl.col("n_events")).alias("proportion"),
                # Cell centroids: lon = x, lat = y
                (cfg.lon_min + (pl.col("cell_lon_idx") + 0.5) * cfg.delta).alias(
                    "x_centroid"
                ),
                (cfg.lat_min + (pl.col("cell_lat_idx") + 0.5) * cfg.delta).alias(
                    "y_centroid"
                ),
            )
            .with_columns(
                (
                    (pl.col("proportion") * (1.0 - pl.col("proportion")))
                    / pl.col("n_events")
                )
                .sqrt()
                .alias("std_dev")
            )
            .collect()
        )

        return df

    def apply_logit_transform(self, df: pl.DataFrame) -> pl.DataFrame:
        """Apply logit transform: logit(p) = log(p / (1-p)).

        Clamps p to [epsilon, 1-epsilon] to avoid log(0).
        Adds 'measurement' column with logit-transformed proportion.
        """
        eps = self.config.logit_epsilon
        df = df.with_columns(
            pl.col("proportion").clip(eps, 1.0 - eps).alias("p_clamped")
        ).with_columns(
            (pl.col("p_clamped") / (1.0 - pl.col("p_clamped")))
            .log()
            .alias("measurement")
        )
        return df.drop("p_clamped")

    def to_exageostat_csv(self, df: pl.DataFrame, output_path=None) -> pl.DataFrame:
        """Export to ExaGeoStatCPP CSV format: x,y,measurement (no header).

        The measurement column is either proportion or logit(proportion)
        depending on config.apply_logit.
        """
        if self.config.apply_logit:
            df = self.apply_logit_transform(df)
        else:
            df = df.with_columns(pl.col("proportion").alias("measurement"))

        export_df = df.select("x_centroid", "y_centroid", "measurement")

        path = output_path or self.config.output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        export_df.write_csv(path, include_header=False)

        return export_df

    def run(self) -> pl.DataFrame:
        """Execute the full binning pipeline: load → filter → bin → aggregate → export."""
        lf = self.load_and_filter()
        lf = self.assign_cells(lf)
        df = self.aggregate(lf)
        self.to_exageostat_csv(df)
        return df
