# results

Committed prediction/diagnostic data and the cross-machine reproduction evidence. Figures
that scripts regenerate here at runtime are git-ignored; the committed thesis figures live
in `figures/`.

## Prediction grids / panels (figure inputs)

| File | Contents |
|------|----------|
| `predictions_rs_detrended.csv` | Detrended (universal) Kriging predictions, 10000-point grid. Columns: `x,y,pred,sd` (no header). Input to Fig 5.6. |
| `predictions_rs_indicator.csv` | Indicator Kriging predictions, same grid/format. Input to Fig 5.7. |
| `predictions_rs_delta002.csv` | Native Kriging predictions at delta=0.02, same grid/format. Input to Fig 5.9. |
| `logit_predictions_utm_grid100.csv` | Logit-model predictions on a 100x100 UTM grid (10000 rows). Columns: `x_km,y_km,logit_pred,var`. Input to Figs 5.3-5.5 (`generate_logit_utm_maps.py`). |

## Diagnostics

| File | Contents |
|------|----------|
| `condition_utm.csv` | Covariance-matrix conditioning at the canonical theta for the logit vs native models (delta=0.05): per row `label, csv, n, sigma2, beta_km, nu, tau2, eig_min, eig_max, cond`. Shows the native model is far worse conditioned (cond ~2.2e5) than the logit model (~8.5e2). |
| `perf_core_sweep.csv` | CPU/GPU core-scaling timings: `backend, cores, gpus, N, dts, iters, seconds` (N=9000). Raw log: `logs/perf_core_sweep_9000.log`. |

## Cross-machine reproducibility

| File / dir | Contents |
|------------|----------|
| `CROSS_MACHINE_SUMMARY.md` | Synthesis: predictions/CV/figures identical across machines; only the non-identifiable MLE (sigma2, beta) varies along the flat likelihood ridge. |
| `cross_machine_comparison.md` | Detailed per-config MLE tables and figure/CV diffs across the three machines. |
| `validation_mac-studio-m1-max/` | Mac Studio (M1 Max) full reproduction: `audit.md`, `cv/`, `predictions/`, `logs/`, `preprocessing/` outputs. |
| `validation_mac-studio-m1-max-run2/` | Same machine, second run (within-machine determinism check). |
| `validation_macbook-pro-m4-pro-1/` | MacBook Pro (M4 Pro) #1 reproduction. |
| `validation_macbook-pro-m4-pro-2/` | MacBook Pro (M4 Pro) #2 reproduction. |

Per-machine map images are not committed (they reproduce the figures already in `figures/`);
the `audit.md` and `cv/`/`predictions/` CSVs carry the comparison. See the root `README.md`
"Cross-machine reproducibility" section for the headline result.

## Provenance

CV/coverage table numbers come from `logs/*_fast.log`, not from any CSV here. The old
degree-coordinate per-fold CSVs (theta = 4.880) are intentionally not committed. See the
root `README.md` provenance section.
