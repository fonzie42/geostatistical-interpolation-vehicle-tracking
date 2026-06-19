# preprocessing

The Python package that turns the raw GPS parquet into ExaGeoStatCPP-ready CSVs, drives the
ExaGeoStat MLE/Kriging, runs the cross-validation, and renders the thesis figures.

Run everything **from the repository root** with the environment from `requirements.txt`
active. The modules import as `preprocessing.<module>` and resolve `data/`, `results/`,
`logs/` relative to the repo root, so running from elsewhere will not find the inputs.

```bash
python -m preprocessing.pipeline --help     # module entry point
python preprocessing/native_cv_utm_fast.py  # script run from the root
```

## 1. Data pipeline (raw parquet -> aggregated CSVs)

| Module | Role |
|--------|------|
| `config.py` | `PipelineConfig` dataclass: grid `delta`, RS bounding box, `min_events` CLT floor, logit toggle, input/output paths. |
| `spatial_binning.py` | `SpatialBinner`: Polars lazy load -> filter to RS -> bin to a `delta` grid -> aggregate to per-cell connectivity proportions -> CSV. |
| `pipeline.py` | CLI wrapper. `python -m preprocessing.pipeline --input <parquet> --delta 0.05 --output data/delta_0.05.csv`. |
| `reproject_to_utm.py` | Reproject the aggregated cells and CV folds from lon/lat (EPSG:4326) to UTM km (EPSG:31982, SIRGAS 2000 / UTM 22S) so distances are isotropic. |
| `prepare_logit_utm.py` | Build the Haldane count-based logit input in UTM (`data/delta_*_logit_utm.csv`), the primary model's ExaGeoStat input. |

See `data/README.md` for the exact end-to-end command sequence and how to obtain the raw
parquet.

## 2. ExaGeoStat interface and prediction

| Module | Role |
|--------|------|
| `exageostat_driver.py` | Subprocess driver for the ExaGeoStatCPP CLI (MLE) and `RPredictor`, which orchestrates Kriging prediction through the R interface in Docker. |
| `predict.R` | R script calling ExaGeoStatCPP's `predict_data()`; returns Kriging predictions. Runs inside the `exageostatcpp:r` image (see `docker/README.md`). |
| `kriging.py` | Pure-Python Matern Kriging (closed form). Used as a fallback/validation and imported by the fast-CV scripts for the prediction step. |

The CLI estimates theta but does not emit predicted values; prediction values come from the
R interface or `kriging.py`. The fast-CV scripts below take a fixed ExaGeoStat theta and do
the closed-form prediction in Python.

## 3. Cross-validation and baselines

These reproduce the CV/coverage tables. They take a fixed theta (from the committed
`logs/mle_*_gpu.log`) and read the committed fold splits in `output/`. Exact commands and
the expected numbers are in the root `README.md` ("Reproducing the tables").

| Module | Role |
|--------|------|
| `native_cv_utm_fast.py` | Spatial-block / leave-fold-out CV for the native (untransformed) model given a theta. |
| `logit_fold_cv_from_logs.py` | **Canonical logit CV.** Uses each fold's own ExaGeoStat MLE theta (parsed from `logs/mle_logit_utm_fold*_gpu.log`); reproduces the global numbers in `logs/logit_cv_utm_fast.log`. |
| `logit_cv_utm_fast.py` | Standalone fast logit CV from one global theta. Needs a `--counts` file (`logit_counts_delta_*_utm.csv`) produced by `prepare_logit_utm.py`; not committed, so prefer `logit_fold_cv_from_logs.py` for the canonical numbers. |
| `baselines_utm_fast.py` | IDW and mean-only baselines under the same CV split. |

## 4. Figures

Figure-by-figure inputs and commands are in `figures/README.md`. Scripts:

| Module | Figure(s) |
|--------|-----------|
| `task7_variogram_utm.py` | 5.2 empirical/fitted variogram (UTM, logit) |
| `generate_logit_utm_maps.py` | 5.3 panel, 5.4 connectivity map, 5.5 uncertainty map |
| `generate_native_panels.py` | 5.6 detrended, 5.7 indicator, 5.9 delta=0.02 panels |
| `reliability_logit.py` | 5.8 reliability + PIT |
| `generate_observations_map.py` | 4.1 observations map |
| `task8_events_per_cell.py` | supporting events-per-cell histogram (needs the raw parquet) |

`visualization.py` holds the shared plotting helpers (heatmaps, comparison panels, RS state
boundary) used by the map scripts.

## 5. Shared utilities

| Module | Role |
|--------|------|
| `visualization.py` | Map/figure rendering helpers, incl. the RS boundary overlay from `data/rs_boundary.geojson`. |
| `validation.py` | `SpatialBlockCV` fold construction and the metric functions (RMSE, MAE, bias, coverage) plus the IDW/mean baselines. |
| `__init__.py` | Marks the package; lets the scripts import siblings as `preprocessing.<module>`. |

## `output/`

Committed cross-validation fold splits consumed by the CV scripts:

- `validate_cv_folds_utm/` -- native model, `fold_NN_{train,test}.csv` (UTM km).
- `validate_cv_folds_logit_utm/` -- logit model, with matching `_truth` files for evaluation
  after back-transformation.

Other pipeline outputs (aggregated cells, regenerated figures) are written here or to
`results/` at runtime and are git-ignored.
