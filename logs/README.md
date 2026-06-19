# logs

Committed run logs. These are the **canonical source** for the thesis numbers:

- **MLE theta** (Table 5.5) come from the ExaGeoStat GPU solver logs, `mle_*_gpu.log`.
- **CV / coverage numbers** (Tables 5.6, 5.7) come from the fast-CV logs, `*_fast.log`.

Prediction given a theta is identical across Python and ExaGeoStat (~1e-12); estimating
theta is an optimizer and differs, so the canonical theta is always the one in these
ExaGeoStat solver logs. Do not recompute the table numbers by re-fitting theta elsewhere
(see the root `README.md` provenance section).

## ExaGeoStat MLE solver logs (theta source)

| Log | Run |
|-----|-----|
| `mle_native_utm_delta005_gpu.log` | native model, delta=0.05 (theta = 1.13654890:453.11557390:0.41416436:0.001) |
| `mle_native_utm_delta002_gpu.log` | native model, delta=0.02 |
| `mle_logit_utm_delta005_gpu.log` | logit model, delta=0.05 |
| `mle_logit_utm_delta002_gpu.log` | logit model, delta=0.02 |
| `mle_logit_utm_delta001_gpu.log` | logit model, delta=0.01 |
| `mle_logit_utm_fold01_gpu.log` ... `fold08_gpu.log` | per-fold logit MLE; the per-fold theta consumed by `logit_fold_cv_from_logs.py` |

Each records the final theta as `--> Final Theta Values (scale, sigma2, nu, tau2)` /
`#Found Maximum Theta at: ...` and the final log-likelihood.

## Fast cross-validation logs (CV / coverage source)

| Log | Produced by | Headline |
|-----|-------------|----------|
| `native_cv_utm_delta005_fast.log` | `native_cv_utm_fast.py` | native, RMSE 0.337, cov 53.4/91.0/96.6/98.3 |
| `native_cv_utm_delta002_fast.log` | `native_cv_utm_fast.py` | native, delta=0.02 |
| `logit_cv_utm_fast.log` | (global-theta logit CV) | logit, RMSE 0.314, cov 56.4/85.1/89.6/91.6 |
| `logit_cv_utm_delta002_fast.log`, `logit_cv_utm_delta001_fast.log` | logit CV at other resolutions |
| `baselines_utm_fast.log` | `baselines_utm_fast.py` | IDW 0.307 / Mean 0.330 (delta=0.02) |
| `baselines_utm_delta001_fast.log` | `baselines_utm_fast.py` | baselines, delta=0.01 |

## Derived / figure logs

| Log | Produced by |
|-----|-------------|
| `logit_fold_cv_from_logs.log` | `logit_fold_cv_from_logs.py` (canonical logit CV; reproduces `logit_cv_utm_fast.log`'s global numbers from the per-fold MLE logs) |
| `task7_variogram_utm.log` | `task7_variogram_utm.py` (Fig 5.2) |
| `generate_logit_utm_maps.log` | `generate_logit_utm_maps.py` (Figs 5.3-5.5) |

## Performance

| Log | Run |
|-----|-----|
| `perf_core_sweep_9000.log` | CPU vs GPU core-scaling sweep (N=9000, dts=320, 20 iters) on the GPU host (NVIDIA RTX 3090). Raw timings behind `results/perf_core_sweep.csv`. |

## Where these ran

The `*_gpu.log` and `perf_core_sweep_9000.log` were produced on the GPU host (Ubuntu x86_64,
NVIDIA RTX 3090, CUDA 11.8) used for theta estimation and the performance section. The
fast-CV and figure logs are pure-Python/CPU and reproduce on any machine. The cross-machine
reproducibility experiment (`results/validation_*/`) is a separate, CPU-only check.

See the root `README.md` ("Reproducing the tables") for the exact commands that regenerate
these logs.
