"""Configuration constants and parameters for the preprocessing pipeline."""

from dataclasses import dataclass, field
from pathlib import Path


# Rio Grande do Sul bounding box (approximate)
RS_LAT_MIN = -33.8
RS_LAT_MAX = -27.0
RS_LON_MIN = -57.7
RS_LON_MAX = -49.5


@dataclass
class PipelineConfig:
    """Configuration for the preprocessing pipeline.

    Attributes:
        input_path: Path to the raw Parquet file.
        output_path: Path for the output CSV (ExaGeoStatCPP format).
        delta: Grid cell size in degrees. Matches Röpke's delta parameter.
        min_events: Minimum number of events per cell for inclusion (CLT).
        apply_logit: Whether to apply logit transform to proportions.
        logit_epsilon: Small value to avoid log(0) in logit transform.
        lat_min, lat_max, lon_min, lon_max: Bounding box for valid points.
        online_max: Maximum valid value for the online column (clamp above).
    """

    input_path: Path = Path("auxiliary_documents/2017-2018-2019-2020.parquet")
    output_path: Path = Path("preprocessing/output/aggregated_cells.csv")
    delta: float = 0.01  # ~1.1 km at RS latitudes
    min_events: int = 30
    apply_logit: bool = False
    logit_epsilon: float = 1e-6
    lat_min: float = RS_LAT_MIN
    lat_max: float = RS_LAT_MAX
    lon_min: float = RS_LON_MIN
    lon_max: float = RS_LON_MAX
    online_max: float = 1.0
