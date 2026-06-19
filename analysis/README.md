# analysis

Supporting analysis used for two thesis figures, kept separate from the main pipeline.

| File | Role |
|------|------|
| `logit_explainer_fig.py` | Generates **Fig 5.1** (the logit-transform explainer: native vs. logit prediction ranges). Reads `predictions_delta005.csv`. `python analysis/logit_explainer_fig.py`. |
| `predictions_delta005.csv` | Long-format per-point predictions at delta=0.05 (`resolution,fold,x,y,true,method,pred,sd,lo95,hi95`). The committed copy is the input for `logit_explainer_fig.py` (Fig 5.1) and for `preprocessing/reliability_logit.py` (Fig 5.8). |
| `run_all.py` | Consolidated single-driver analysis: re-aggregates per-cell counts from the raw parquet, builds the 3x3 spatial-block folds in code, runs every method (mean, IDW, native Kriging, logit Kriging) at delta=0.05 and 0.02, and writes the per-point predictions, a metrics summary, theta estimates, and the reliability/variogram/events figures into this folder. Needs the raw parquet. |

## Provenance caveat (important)

`run_all.py` **re-fits theta in Python**. It is convenient for the illustrative figures, but
its theta and metrics are **not** the canonical thesis numbers. The thesis CV/coverage
numbers come only from the committed fast-CV logs in `logs/` (which use the ExaGeoStat MLE
theta), and the MLE theta come from `logs/mle_*_gpu.log`.

Kriging prediction *given* a theta is identical across Python and ExaGeoStat (~1e-12), but
*estimating* theta is an optimizer and differs, so the canonical theta is always
ExaGeoStat's. Use `preprocessing/logit_fold_cv_from_logs.py` and the other `*_fast.py`
scripts (which consume the ExaGeoStat theta) for the table numbers, not `run_all.py`. See
the root `README.md` provenance section.
