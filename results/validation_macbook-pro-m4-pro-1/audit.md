# Validation Audit Log

## Machine Info
- **Machine ID**: MacBook Pro (M4 Pro) #1
- **Hardware**: Mac (Apple Silicon, T6041 / M4 Pro family), 24 GB RAM
- **OS**: Darwin 25.4.0 Darwin Kernel Version 25.4.0: Thu Mar 19 19:33:25 PDT 2026; root:xnu-12377.101.15~1/RELEASE_ARM64_T6041 arm64
- **Docker version**: Docker version 29.5.3, build d1c06ef
- **Docker RAM allocation**: 18.83 GB (MemTotal 18831835136 bytes)
- **Python version**: Python 3.14.5 (system); venv will be created
- **Git commit**: de8411b8ff0233b187c8dbbbb1a0c0d2bd506e0e
- **Git branch**: fixes
- **Validation started**: 2026-06-09T03:41:40Z
- **Validation ended**: 2026-06-09T15:31:52Z (~11.8 h wall-clock, dominated by the 8.5 h delta=0.02 MLE)

## Results Summary
| Step | Status | Duration | Notes |
|------|--------|----------|-------|
| Pre-Tier | PASS | - | VDIR created, Docker RAM 18.83 GB > 17 GB OK |
| T0.1 | PASS | ~10s | 68 passed, 0 failed (pytest not in requirements.txt, installed separately) |
| T0.2 | PASS | <1s | All 7 MD5 match, line counts match |
| T0.3 | PASS* | ~1min | Content bit-identical (max diff 0.0 sorted); row ORDER differs (non-determ. Polars agg) |
| T0.4 | PASS | ~3min | All 5 deltas match Table 4.1 cell counts + mean proportions exactly |
| T0.5 | PASS | <1s | R^2=0.102338, coeffs max diff 5e-11 |
| T0.6 | PASS | <1s | 8 folds, all sizes match, diff 0.0 |
| T1.1 | PASS | ~12min | CPU 1.95GB + R 2.21GB built (1st CPU attempt timed out on base-image pull; pre-pulled then OK) |
| T1.2 | PASS | ~30s | pred(0.25,0.25)=1.1829534281 for N=1,3,5; diff 4.28e-7; invariant. predict.R was a 7-byte stub, restored to 248 lines |
| T1.3 | PASS | ~30s | No crash, 5 iter lines, "Found Maximum Theta" present, LL=-6180.35 (not converged @5, expected) |
| T2.1 | PASS* | 48min | LL reproduced (1101.63 vs 1100.90, marginally better), nu/tau2 match, microergodic 0.56%. DIFFERENT ridge point: sigma2=2.77/beta=7.82 vs 4.88/14.80. Strict per-param criteria N/A (anticipated) |
| T3.1a | PASS* | 18min | no-nugget: LL 1105.37 vs 1105.9, nu match, microergodic 0.67%; ridge sigma2=3.87/beta=12.66 |
| T3.1b | PASS* | 19min | detrended: LL 1102.77 vs 1103.0, nu+tau2 match, microergodic 0.27%, iters 193 vs 192 |
| T3.1c | PASS* | 13min | indicator: LL -2449.46 vs -2449.49 (d 0.03!), microergodic 0.48% |
| T3.2a | PASS | 38s | Simple Kriging grid: max diff 4.86e-12 vs original |
| T3.2b | PASS | ~40s | Universal (detrended+trend) final: max diff 5.05e-11 |
| T3.2c | PASS* | ~40s | Indicator: 9.78e-7 vs Studio (ill-conditioned); bit-identical run-to-run on Pro |
| T3.3a | PASS | ~3min | Simple CV: wt RMSE_K=0.344, RMSE_R=0.429, impr 19.9%, cov 98.7%, exact Table 5.3 |
| T3.3b | PASS | ~3min | Universal CV: wt RMSE_K=0.341 (exp 0.341) |
| T3.3c | PASS | ~3min | Indicator CV: wt RMSE_K=0.420 (exp 0.420) |
| T3.4 | PASS | ~15s | All 6 figures regenerated; visual + CSV match (originals are .svg not .png) |
| T4.1 | PASS* | 8h30m | delta=0.02 MLE: 287 iters (exp 288!), LL 5855.12 vs 5854.25, nu 0.3935 vs 0.393 + tau2 match, microergodic 0.51%; ridge sigma2=1.54/beta=4.96 |
| T4.2 | PASS | ~3min | delta=0.02 prediction: max diff 4.77e-12 vs original; Fig 5.6 generated + verified |

## Detailed Results

### Pre-Tier: Setup
- Validation output directory: `results/validation_macbook-pro-m4-pro-1`
- Docker MemTotal: 18831835136 bytes (~18.83 GB), exceeds the 17 GB requirement for Tier 4.
- PASS

### Tier 0: Input Validation: ALL PASS

**T0.1**: venv created (Python 3.14.5). `pytest` was NOT in `preprocessing/requirements.txt`, so it was installed separately (`pip install pytest`). Result: **68 passed in 8.85s, 0 failures**. PASS.

**T0.2**: All 7 MD5 checksums match the plan exactly:
- delta_0.05.csv `6093efde45787c44517d8a7031e53046` (5401 lines) ✓
- delta_0.02.csv `251206a24979a45202c7da3bffdbd8f8` (16922 lines) ✓
- delta_0.05_detrended.csv `a5b99fe4aebc09520dfc84a6f900813a` ✓
- binary_sample_5401.csv `4a4bbee4dbf4447e81aac741559c84c0` (5401 lines) ✓
- train_test4.csv `c9ef36237fb65c678e7f0f135fee8e97` ✓
- test_test4.csv `6202c0d2c563de19f1bbe74cc51a4bdf` ✓
- trend_coeffs_delta_0.05.csv `d344de7e753782758fa66e4b0355a9bb` (6 lines) ✓
PASS.

**T0.3**: Regenerated delta_0.05.csv (5401 cells, mean 0.6044) and delta_0.02.csv (16922 cells, mean 0.6130) from the Parquet.
- `diff` against originals is NON-empty: rows are emitted in a **different order**.
- **FINDING (differs from Mac Studio (M1 Max))**: On Mac Studio (M1 Max) the regenerated CSVs were byte-identical to the originals. On this machine the row ORDER differs, the Polars groupby/aggregation does not guarantee a stable output order across machines/versions.
- Numerical content is **bit-identical**: after lexicographic sort by (x,y), max abs diff = 0.000e+00 for BOTH deltas.
- This is numerically irrelevant downstream: the Gaussian log-likelihood and Kriging predictions are invariant under row permutation (covariance matrix is just permuted). PASS (content).

**T0.4**: All 5 deltas match Table 4.1 exactly:
| delta | Cells (obs) | Cells (exp) | Mean prop (obs) | Mean prop (exp) |
|-------|-------------|-------------|-----------------|-----------------|
| 0.005 | 67,880 | 67,880 | 0.645 | 0.645 |
| 0.010 | 36,025 | 36,025 | 0.624 | 0.624 |
| 0.020 | 16,922 | 16,922 | 0.613 | 0.613 |
| 0.050 | 5,401 | 5,401 | 0.604 | 0.604 |
| 0.100 | 2,074 | 2,074 | 0.604 | 0.604 |
PASS.

**T0.5**: R^2 = 0.102338 (within 0.01 of 0.10), coeffs max diff vs stored = 5.00e-11 (< 1e-8). PASS.

**T0.6**: 8 folds generated, all sizes match expected [249,15,395,852,799,463,1789,839], every fold diff = 0.0 vs committed splits. PASS.

### Tier 1: Docker Smoke Test: ALL PASS

**T1.1**: Build both images.
- First CPU build attempt FAILED: `DeadlineExceeded: context deadline exceeded` while loading metadata for `ubuntu:22.04` (registry/network timeout, ~1 min). **Workaround**: `docker pull --platform linux/amd64 ubuntu:22.04` to cache the base image, then rebuilt, succeeded (full 10161-line from-source build, exit 0).
- Images: `exageostatcpp:cpu` (1.95 GB, binary present, built today), `exageostatcpp:r` (2.21 GB, exit 0).
PASS.

**T1.2**: Bug regression test (Table 4.5).
- **Pre-step issue**: `data/predict.R` was a 7-byte stub (modified 00:43 today, not the committed version). Restored with `git checkout HEAD -- data/predict.R` → 248 lines.
- Canonical test: train=micro_train.csv, theta=1.0:0.5:0.5:0.01, dts=10, eval at (0.25,0.25) for N_test=1,3,5.
- Result: pred(0.25,0.25) = **1.1829534281** for ALL three N_test sizes. Max diff vs 1.182953 = 4.28e-07 (< 1e-4). Invariant across N_test (the actual bug that was fixed). PASS.

**T1.3**: MLE 5-iteration sanity (delta=0.05 nuggets). No crash, exit 0, 5 iteration lines present, `#Found Maximum Theta at:` present, `#Final Log Likelihood value: -6180.348488` (not converged at 5 iters, as expected). Output format correct. PASS.

### Tier 2: Baseline MLE: PASS* (likelihood reproduced, different ridge point)

**T2.1**: Baseline MLE, delta=0.05, `univariate_matern_nuggets_stationary`, 48 min wall-clock, 491 iterations, exit 0.

| param | Pro (observed) | Studio/thesis (expected) | verdict |
|-------|---------------|--------------------------|---------|
| sigma2 | 2.7651 | 4.880 | DIFFERS (ridge) |
| beta | 7.8178 | 14.799 | DIFFERS (ridge) |
| nu | 0.4528 | 0.452 | MATCH (diff 0.0008) |
| tau2 | 0.0010 | 0.001 | MATCH |
| LogLik | 1101.6297 | 1100.904 | reproduced, +0.726 (marginally better optimum) |
| iters | 491 | 298 | differs |

- **Microergodic parameter sigma2/beta^(2nu): Pro = 0.42951, Studio = 0.42710, relative diff 0.56% (< 1%).**
- **This is the MAIN NEW INFORMATION the plan asked for**: MacBook Pro (M4 Pro) #1 lands on a **DIFFERENT ridge point** than Mac Studio (M1 Max) (sigma2≈2.77/beta≈7.82 vs ≈4.74-4.88/≈14.58-14.80). This confirms the likelihood ridge for (sigma2, beta) is genuinely flat and weakly identified, independent machines find different individual parameters but the same microergodic quantity and an equivalent (here marginally higher) log-likelihood.
- The strict per-parameter PASS criteria (sigma2 ±0.001, iter=298 exact) are NOT met, but the plan explicitly anticipates this ("the individual (sigma2, beta) and iteration counts may differ, they sit on a flat, weakly-identified likelihood ridge"). This does NOT trigger the fail-fast STOP: the log-likelihood and microergodic parameter, the identifiable quantities, are reproduced, and all Tier 3 predictions/CV use the FIXED thesis theta (not this re-estimate), so they remain exactly reproducible. PASS*.

### Tier 3: Predictions, CV, Figures: ALL PASS (T3.1 MLEs still running)

**T3.2 Kriging grid predictions** (all use FIXED thesis theta, grid-res 100 = 10000 points):
- **T3.2a Simple** (theta 4.880:14.799:0.452:0.001): pred range [-0.320, 1.021], var [0.0036, 1.542]. Max diff vs `results/predictions_rs.csv`: pred 4.86e-12, var 1.70e-14. PASS.
- **T3.2b Universal/detrended** (theta 1.646:4.288:0.456:0.001) + quadratic trend reconstruction: final-pred max diff vs original 5.05e-11. PASS.
- **T3.2c Indicator** (theta 0.509:144.73:0.133:0.09): pred max diff 9.78e-07, var 1.45e-06 vs `results/predictions_rs_indicator.csv`.
  - **FINDING (cross-machine precision)**: Re-ran on Pro → run1 vs run2 = **0.0 (bit-identical)**, so the pipeline is deterministic WITHIN a machine. The 9.78e-07 is a STABLE Pro-vs-Studio difference. The indicator config is ill-conditioned (beta=144.73 huge range, nu=0.133, near-singular covariance), which amplifies ~1e-15 ULP differences between the two machines' emulated-amd64 FP into ~1e-6 in the solve. Well-conditioned configs (simple 4.9e-12, detrended 5.1e-11) stay at machine epsilon. 9.78e-7 is 6 significant figures, far below the thesis's 3-decimal reported precision and invisible in figures. PASS* (scientific reproduction; exceeds strict 1e-8 only for the ill-conditioned system).

**T3.3 Cross-validation** (fixed thesis theta per variant):
- **T3.3a Simple (8 folds)**: every per-fold RMSE_K matches Table 5.3 to 3 decimals. Weighted RMSE_K=0.344 (exp 0.344), RMSE_R=0.429 (exp 0.429), MAE_K=0.293, MAE_R=0.326, Cov95=98.7% (exp 98.7%), improvement=19.9% (exp 19.9%). PASS.
- **T3.3b Universal (8 folds)**: weighted RMSE_K=0.341 (exp 0.341), RMSE_R=0.428, Cov 98.7%, improvement 20.3%. PASS.
- **T3.3c Indicator (9 folds, 00-08)**: weighted RMSE_K=0.420 (exp 0.420), RMSE_R=0.531, Cov 99.8%, improvement 21.0%. PASS.
- Matches Table 5.5 (Simple 0.344 / Universal 0.341 / Indicator 0.420) exactly.

**T3.4 Figures**: All 6 figures (4.1, 5.1-5.5) regenerated from validated prediction CSVs (PNG + SVG). NOTE: the plan's table lists `.png` originals but the committed originals are `.svg` (e.g. `results/painel_comparativo_boundary.svg`). Visual spot-check (rendered original SVG via qlmanage vs new PNG) confirms identical RS boundary, identical observed-proportion scatter, identical color scales. Combined with byte-identical source CSVs, figures reproduce. PASS. (Fig 5.6 / delta=0.02 deferred to Tier 4.)

**T3.1 MLE configs** (no-nugget / detrended / indicator):

- **HICCUP (transient, resolved)**: The first chained launch ran CONCURRENTLY with the foreground T3.2/T3.3/T3.4 Docker containers. The no-nugget MLE aborted almost immediately with `std::domain_error: You need to set the Dense tile size, before starting`, even though `--dts=320` was present in the logged command, and the container then hung (entrypoint stayed alive after the C++ abort), so `docker run` never returned and the chained loop stalled for ~1 hour. 
- **Diagnosis**: Not an argument-parsing bug. The error is thrown in `Configurations.cpp:202` when `GetDenseTileSize()==0`. Re-running the SAME command (both the plan's order and my appended-`$COMMON` order) in isolation → `#Dense Tile Size: 320`, iterates fine. The crash was a transient startup failure under heavy concurrent Docker load (multiple `docker run` launching at once oversubscribing 14 cores / 17 GB). **Lesson for operators: do NOT launch the MLE chain concurrently with foreground Docker prediction jobs.**
- **Resolution**: killed the hung container + stalled task, relaunched the 3 MLEs chained with NO concurrent foreground Docker. All three completed clean (exit 0): no-nugget 18 min, detrended 19 min, indicator 13 min.

Results (all PASS*, log-likelihood + microergodic + nu/tau2 reproduced, sigma2/beta on the ridge):

| config | sigma2 (obs/exp) | beta (obs/exp) | nu (obs/exp) | tau2 | LogLik (obs/exp, diff) | iters (obs/exp) | microergodic rel.diff |
|--------|------------------|----------------|--------------|------|------------------------|-----------------|-----------------------|
| T3.1a no-nugget | 3.867 / 2.654 | 12.656 / 8.14 | 0.4406 / 0.442 | n/a | 1105.37 / 1105.9 (−0.53) | 180 / 152 | **0.67%** |
| T3.1b detrended | 1.795 / 1.646 | 4.755 / 4.29 | 0.4546 / 0.456 | 0.001/0.001 | 1102.77 / 1103.0 (−0.23) | 193 / 192 | **0.27%** |
| T3.1c indicator | 0.468 / 0.509 | 139.82 / 144.73 | 0.1258 / 0.133 | 0.087/0.090 | −2449.46 / −2449.49 (+0.03) | 141 / 109 | **0.48%** |

**Conclusion across all 4 MLE configs (T2.1 + T3.1a/b/c)**: the identifiable quantities, Gaussian log-likelihood (all within 0.73), smoothness nu (within 0.007), nugget tau2 (exact), and the microergodic parameter sigma2/beta^(2nu) (all within 0.67%), reproduce across machines. The variance sigma2 and range beta individually do NOT (they trade off along a flat likelihood ridge), and iteration counts differ. This is the documented, expected weak-identifiability behavior, and crucially the thesis's KRIGING results all use fixed thesis theta, so they are unaffected.

### Tier 3 OVERALL: PASS: predictions, CV, figures reproduce exactly; MLEs reproduce all identifiable quantities.

### Tier 4: delta=0.02 Full Run (N=16922)

**T4.1 MLE**, 8h30m wall-clock, single-threaded StarPU, mem peak ~2.25 GB (matches plan's ~2.3 GB note; the 17 GB allocation was never approached), exit 0.

| param | Pro (obs) | thesis (exp) | verdict |
|-------|-----------|--------------|---------|
| sigma2 | 1.5439 | 2.438 | DIFFERS (ridge) |
| beta | 4.9593 | 8.943 | DIFFERS (ridge) |
| nu | 0.3935 | 0.393 | MATCH |
| tau2 | 0.0010 | 0.001 | MATCH |
| LogLik | 5855.124 | 5854.25 | reproduced (+0.87, marginally better) |
| iters | **287** | 288 | essentially exact (±1) |

- Microergodic sigma2/beta^(2nu) = 0.43791 vs 0.43568, **rel.diff 0.51%** (< 1%).
- Same weak-identifiability pattern as the N=5401 configs: log-likelihood, nu, tau2, microergodic param, and even the iteration count (287 vs 288) reproduce; the (sigma2, beta) pair sits at a different ridge point. PASS*.
- Operational note: stdout is block-buffered when redirected; the first ~37 iterations were invisible until the libc buffer flushed. Mid-run progress monitored via `ps` (PID 1 at 100% CPU) instead.

**T4.2 Prediction** (fixed thesis theta 2.438:8.943:0.393:0.001, N=16922 train, grid-res 100): exit 0, pred range [-0.083, 1.009], var [0.0042, 1.278]. Max diff vs `results/predictions_rs_delta002.csv`: pred 4.77e-12, var 9.99e-15. PASS (well-conditioned, reproduces at machine epsilon, unlike the ill-conditioned indicator config).

**Fig 5.6** (delta=0.02 panel): generated from validated CSV, renders the finer-resolution connectivity structure; visually consistent with the delta=0.05 panels at higher detail. All 7 thesis figures now reproduced.

### Tier 4 OVERALL: PASS.

---

## FINAL VERDICT (MacBook Pro (M4 Pro) #1)

**All thesis results reproduced: YES.** Every tier passed. No fail-fast STOP was triggered.

### Deterministic results: reproduce EXACTLY (use fixed thesis theta):
| Result | Max diff vs original | Status |
|--------|----------------------|--------|
| Bug regression pred(0.25,0.25)=1.182953 | 4.3e-7, invariant across N_test | PASS |
| Simple Kriging grid (predictions_rs) | pred 4.86e-12, var 1.70e-14 | PASS |
| Universal Kriging grid (detrended_final) | 5.05e-11 | PASS |
| Indicator Kriging grid | 9.78e-7 (cross-machine, ill-conditioned) | PASS* |
| delta=0.02 grid (predictions_rs_delta002) | pred 4.77e-12, var 9.99e-15 | PASS |
| Simple CV (Table 5.3) | weighted RMSE_K 0.344 / RMSE_R 0.429 / impr 19.9% / cov 98.7% | EXACT |
| Variant CV (Table 5.5) | Simple 0.344 / Universal 0.341 / Indicator 0.420 | EXACT |
| Preprocessing (Table 4.1) | all 5 deltas, cell counts + proportions | EXACT |
| All 7 figures | visual + source-CSV match | PASS |

### MLE results: reproduce all IDENTIFIABLE quantities (<1%); (sigma2,beta) ride a flat likelihood ridge:
| Config | LogLik (obs/exp) | nu match | microergodic rel.diff | sigma2,beta vs thesis |
|--------|------------------|----------|-----------------------|------------------------|
| Baseline (5.2) | 1101.63 / 1100.90 | 0.4528/0.452 | 0.56% | 2.77,7.82 vs 4.88,14.80 |
| No-nugget | 1105.37 / 1105.9 | 0.4406/0.442 | 0.67% | 3.87,12.66 vs 2.65,8.14 |
| Detrended | 1102.77 / 1103.0 | 0.4546/0.456 | 0.27% | 1.80,4.76 vs 1.65,4.29 |
| Indicator | -2449.46 / -2449.49 | 0.1258/0.133 | 0.48% | 0.47,139.8 vs 0.51,144.7 |
| delta=0.02 | 5855.12 / 5854.25 | 0.3935/0.393 | 0.51% | 1.54,4.96 vs 2.44,8.94 |

### Key findings (new information from this 2nd machine):
1. **MLE ridge non-identifiability confirmed.** MacBook Pro (M4 Pro) #1 lands on DIFFERENT (sigma2, beta) ridge points than Mac Studio (M1 Max) for every config, while reproducing the log-likelihood (all within 0.9), smoothness nu (within 0.007), nugget tau2 (exact), and the microergodic parameter sigma2/beta^(2nu) (all within 0.67%). This is strong cross-machine evidence that the (sigma2, beta) ridge is genuinely flat and weakly identified, a substantive result for the thesis's discussion of parameter identifiability. Iteration counts are nonetheless close (detrended 193/192, delta=0.02 287/288).
2. **Cross-machine FP reproducibility is exact for well-conditioned systems, ~1e-6 for the ill-conditioned indicator system.** Within a single machine the Kriging pipeline is bit-identical (run-to-run diff 0.0). Across machines, well-conditioned configs match at machine epsilon (1e-11..1e-12); only the near-singular indicator config (beta=144.7) amplifies ULP differences to ~1e-6, still 6 significant figures, far below the thesis's 3-decimal reported precision and invisible in figures.
3. **Crucially, the thesis's Kriging results are unaffected by finding #1** because every prediction/CV uses the FIXED thesis theta, not a re-estimate.

### Operational notes / hiccups (thesis "journey" material):
- `pytest` is not listed in `preprocessing/requirements.txt` (installed separately for T0.1).
- Preprocessing CSV row ORDER is non-deterministic across machines (Polars aggregation); content bit-identical; downstream-irrelevant (permutation-invariant).
- First CPU Docker build timed out pulling `ubuntu:22.04` metadata; fixed by `docker pull` then rebuild.
- `data/predict.R` was a 7-byte stub at session start; restored to the real 248-line script via `git checkout HEAD --`.
- The T3.1 MLE chain hit a transient `set the Dense tile size` abort + container hang when launched CONCURRENTLY with foreground prediction Docker jobs; not reproducible in isolation. Lesson: do not run the MLE chain alongside other Docker workloads.
- delta=0.02 MLE: single-threaded StarPU, 8.5 h, peak ~2.25 GB (17 GB allocation never approached); stdout block-buffered (monitor via `ps`, not the log, mid-run).
- Thesis figure originals are committed as `.svg`, not `.png` as the plan's table lists.
