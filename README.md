# Geostatistical Interpolation of Vehicle-Tracking Data

Companion code and data for the TCC applying Kriging (via ExaGeoStatCPP) to vehicle-tracking
GPS connectivity data from Rio Grande do Sul, Brazil. It contains the preprocessing
pipeline, the Maximum Likelihood Estimation (MLE) and Kriging workflow, the
cross-validation and calibration scripts, and the scripts that generate every figure in
the thesis, together with the aggregated inputs and the canonical logs needed to reproduce
the tables.

## What the project does

Binary online/offline GPS observations (66.3M rows) are spatially aggregated into grid-cell
connectivity proportions. By the Central Limit Theorem, a cell's proportion (mean of many
0/1 observations) is approximately Gaussian, which justifies Gaussian-process Kriging. The
proportions are fed into ExaGeoStatCPP for MLE parameter estimation and Kriging prediction.
The primary model works on the Haldane-logit of the proportion in UTM coordinates; a native
(untransformed) model and IDW / mean baselines are kept for comparison.

## Repository layout

```
docker/         Dockerfiles, compose, entrypoint that build the ExaGeoStatCPP engine + docker/README.md
preprocessing/  Python pipeline, CV/metrics scripts, figure scripts, predict.R + preprocessing/README.md
  output/       CV fold splits (committed inputs to the CV scripts)
data/           Aggregated CSV inputs (+ UTM and logit-UTM variants) + data/README.md
results/        Prediction/diagnostic CSVs + cross-machine summaries +
                validation_<machine>/ per-machine reproduction folders
                (script-regenerated images here are git-ignored; committed copies in figures/)
logs/           Canonical fast-CV logs and ExaGeoStat MLE GPU logs (source of the tables) + logs/README.md
figures/        Final thesis figures (PNG) + figures/README.md (figure -> script -> command).
                Holds exactly the images referenced in the thesis .tex, one copy each.
analysis/       logit explainer figure (Fig 5.1) + reliability inputs + analysis/README.md
requirements.txt
```

## Setup

### Python (preprocessing, CV, figures)

```bash
python3 -m venv .venv
source .venv/bin/activate        # bash/zsh; fish: source .venv/bin/activate.fish
pip install -r requirements.txt
```

Run all Python scripts **from the repository root** (they use repo-root-relative paths and
import the `preprocessing` package).

### Docker (ExaGeoStatCPP engine)

The MLE and the R-interface Kriging run inside ExaGeoStatCPP Docker images. Those images
build the C++ framework, not this repo:

- Fork used for this thesis (the Docker build source): <https://github.com/fonzie42/ExaGeoStatCPP>
- Official upstream project: <https://github.com/ecrc/ExaGeoStatCPP>

See **`docker/README.md`** for build context, build commands, and run examples.

## End-to-end run order

1. **Obtain the raw parquet** and place it at `auxiliary_documents/2017-2018-2019-2020.parquet`
   (not committed; see `data/README.md`).
2. **Aggregate** raw points into cell proportions, then reproject and build the logit input:
   ```bash
   python -m preprocessing.pipeline --input auxiliary_documents/2017-2018-2019-2020.parquet --delta 0.05 --output data/delta_0.05.csv
   python preprocessing/reproject_to_utm.py
   python preprocessing/prepare_logit_utm.py
   ```
   (The aggregated CSVs are already committed in `data/`, so steps 1-2 are only needed to
   regenerate them from scratch.)
3. **Estimate theta (MLE)** with ExaGeoStatCPP (GPU image; produces the `mle_*_gpu.log`
   logs). See `docker/README.md`.
4. **Predict (Kriging)** via the ExaGeoStatCPP R interface (`preprocessing/predict.R`,
   R image) using the estimated theta.
5. **Cross-validation / metrics** (fast, pure-Python given a fixed theta): see the table
   below.
6. **Figures**: see `figures/README.md`.

## Reproducing the tables

| Thesis table | Source | How to reproduce |
|--------------|--------|------------------|
| 5.5 (MLE configs) | ExaGeoStat MLE theta in `logs/mle_*_gpu.log` | read theta from the logs (e.g. `mle_native_utm_delta005_gpu.log`, `mle_logit_utm_delta005_gpu.log`) |
| 5.6 (variants CV: RMSE/MAE/bias/coverage) | fast-CV logs in `logs/` | the CV commands below regenerate the numbers in those logs |
| 5.7 (calibration / coverage) | `logs/logit_cv_utm_fast.log` + `preprocessing/reliability_logit.py` | logit CV command below + the reliability figure |

CV commands (run from repo root; each was verified to reproduce its committed log):

```bash
# Native model, delta=0.05 (theta from mle_native_utm_delta005_gpu.log)
python preprocessing/native_cv_utm_fast.py \
    --theta 1.13654890:453.11557390:0.41416436:0.00100000 --mode folds \
    --fold-dir preprocessing/output/validate_cv_folds_utm
# -> RMSE 0.337, coverage 53.4 / 91.0 / 96.6 / 98.3 (cov50/80/90/95)

# Logit model (canonical, per-fold theta from the MLE logs)
python preprocessing/logit_fold_cv_from_logs.py
# -> RMSE 0.314, coverage 56.4 / 85.1 / 89.6 / 91.6

# IDW / mean baselines (delta=0.02 by default)
python preprocessing/baselines_utm_fast.py
# -> IDW RMSE 0.307, Mean RMSE 0.330
```

## CRITICAL: results provenance

The thesis CV/coverage numbers come **only** from the committed fast-CV logs in `logs/`
(`native_cv_utm_delta005_fast.log`, `logit_cv_utm_fast.log`, `baselines_utm_fast.log`, and
the `*_delta002_fast.log` variants). The MLE theta come from the ExaGeoStat GPU logs
(`mle_*_gpu.log`).

Do **not** recompute thesis numbers from `results/cv_pred_fold_*.csv` (those used an old
degree-coordinate theta = 4.880) or by re-fitting theta in Python (e.g. via
`analysis/run_all.py`). Kriging prediction *given* a theta is identical
across Python and ExaGeoStat (agrees to ~1e-12), but *estimating* theta is an optimizer and
differs between implementations, so the canonical theta is always ExaGeoStat's. The
`*_fast.py` CV scripts here take theta as input (from the ExaGeoStat MLE logs) precisely so
prediction is reproduced without re-fitting.

## Cross-machine reproducibility

The thesis includes a cross-machine reproducibility check. The same Docker images, git
commit, and input data were run independently on three Apple Silicon machines (a Mac Studio
M1 Max and two MacBook Pro M4 Pro, x86_64 under Rosetta 2 emulation), with the Mac Studio
also run twice as a within-machine determinism check. Predictions, CV, and figures are
bit-for-bit identical across machines because they use the fixed thesis theta; the only
variation is in the individually non-identifiable MLE parameters, fully explained by the
flat likelihood ridge.

The evidence lives under `results/`:

- `CROSS_MACHINE_SUMMARY.md`, `cross_machine_comparison.md`: the synthesis (tables of the
  per-machine results).
- `validation_<machine>/`: one folder per machine with the quantitative evidence,
  `audit.md`, the per-fold `cv/` outputs, `predictions/`, `logs/`, and the `preprocessing/`
  outputs for that run. `validation_mac-studio-m1-max-run2/` is the determinism re-run. The
  per-machine map images are not included (they reproduce the same figures already in
  `figures/`); the `audit.md` and the `cv/`/`predictions/` CSVs carry the comparison.

## Notes and caveats

- `logit_fold_cv_from_logs.py` is the canonical logit-CV reproducer; it reads the per-fold
  MLE logs (`logs/mle_logit_utm_fold*_gpu.log`) and the fold splits, and reproduces the
  global numbers in `logit_cv_utm_fast.log` exactly.
- `logit_cv_utm_fast.py` (the standalone fast logit CV) requires a `--counts` file
  (`logit_counts_delta_*_utm.csv`) that is regenerated by `prepare_logit_utm.py`; it is not
  committed here. Use `logit_fold_cv_from_logs.py` for the canonical numbers.
- `preprocessing/task8_events_per_cell.py` needs the raw 1 GB parquet and so cannot run from
  the committed inputs alone.
