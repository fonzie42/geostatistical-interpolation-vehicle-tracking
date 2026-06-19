# Data

The committed files here are the **aggregated** inputs to the geostatistical pipeline,
small enough to version. The 1 GB raw GPS parquet is **not** committed (see below).

## Committed aggregated inputs

| File | What it is |
|------|------------|
| `delta_0.05.csv` | Cell-aggregated connectivity proportions, grid cell delta = 0.05 deg (~5.6 km), 5401 cells. Format: `lon,lat,proportion` (no header). |
| `delta_0.02.csv` | Same, delta = 0.02 deg (~2.2 km), 16922 cells. |
| `delta_0.05_utm.csv` | `delta_0.05.csv` reprojected to UTM (EPSG:31982, SIRGAS 2000 / UTM 22S), coordinates in km. The native-model ExaGeoStat input. |
| `delta_0.02_utm.csv` | `delta_0.02.csv` reprojected to UTM (km). |
| `delta_0.05_logit_utm.csv` | UTM coordinates with the Haldane-logit-transformed proportion as the measurement. The primary (logit) ExaGeoStat input. |
| `binary_sample_5401.csv` | A binary (0/1) indicator sample used for the indicator-Kriging comparison panel (Fig 5.7). |
| `trend_coeffs_delta_0.05.csv` | Quadratic trend coefficients used to add the trend back to the detrended residual predictions (Fig 5.6). |
| `rs_boundary.geojson` | Rio Grande do Sul state outline (from IBGE). Drawn as the map border on Figs 5.3-5.9. The map scripts skip the border silently if it is missing, so the regenerated maps would not match the thesis without it. |

Coordinate convention follows ExaGeoStatCPP's CSV loader: no header, comma-separated,
columns `x, y, measurement`.

## Raw data (not committed)

`2017-2018-2019-2020.parquet` (~1 GB, 66,266,467 rows). Columns: `latitude` (Float64),
`longitude` (Float64), `online` (Float64). Vehicle-tracking online/offline observations
from Rio Grande do Sul, Brazil. Spatial extent: lat [-33.80, -27.00], lon [-57.74, -49.50].

Obtain it from the thesis author / data provider and place it at the path the config
expects:

```
auxiliary_documents/2017-2018-2019-2020.parquet
```

(or pass an explicit `--input` path to the pipeline).

## Regenerating the aggregated CSVs from the raw parquet

```bash
# 1. Aggregate raw points into cell proportions (lon/lat degrees)
python -m preprocessing.pipeline --input auxiliary_documents/2017-2018-2019-2020.parquet \
    --delta 0.05 --min-events 30 --output data/delta_0.05.csv
python -m preprocessing.pipeline --input auxiliary_documents/2017-2018-2019-2020.parquet \
    --delta 0.02 --min-events 30 --output data/delta_0.02.csv

# 2. Reproject the aggregated CSVs (and CV folds) to UTM km
python preprocessing/reproject_to_utm.py

# 3. Build the Haldane-logit count-based UTM input (primary model)
python preprocessing/prepare_logit_utm.py
```

`min_events` (default 30) is the CLT floor: cells with fewer observations are dropped so
the per-cell proportion is a trustworthy mean. The Haldane-logit transform uses
`logit_epsilon = 1e-6` to avoid `log(0)` at proportions of exactly 0 or 1.
