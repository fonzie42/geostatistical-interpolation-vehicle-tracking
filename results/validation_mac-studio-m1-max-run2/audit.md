# Validation Audit Log: RUN 2

Second independent full run on the SAME machine (Mac Studio (M1 Max)), executed while
a different machine runs in parallel. Purpose: within-machine reproducibility check
(does a fresh Docker rebuild + fresh run reproduce RUN 1 bit-for-bit?). RUN 1 lives
in results/validation_mac-studio-m1-max/ and is NOT modified.

## Machine Info
- **Machine ID**: Mac Studio (M1 Max) run 2
- **Hardware**: Mac Studio (Apple Silicon, T6000 = M1 Max), 32GB RAM
- **OS**: Darwin 24.6.0 arm64
- **Docker version**: 29.2.0; Docker RAM allocation: 25.2GB
- **Python**: 3.14.0 (venv .venv/)
- **Git commit**: de8411b8ff0233b187c8dbbbb1a0c0d2bd506e0e
- **Git branch**: fixes
- **Validation started**: 2026-06-09T03:45:31Z
- **Validation ended**: 2026-06-09T16:26:17Z

Note: RUN 1 was at commit c4d9f62; RUN 2 at de8411b. The commits in between only
touched docs/.gitignore/results/data-csv/settings, NONE affect the Docker image
(src/inst unchanged), so the rebuilt image should be source-identical.

## Results Summary
| Step | Status | run2 vs thesis/orig | run2 vs RUN 1 |
|------|--------|---------------------|---------------|
| T0.1 | PASS | 68 passed | (same) |
| T0.2 | PASS | 7/7 MD5 match | (same) |
| T0.3 | PASS | max diff 0 vs orig | bit-identical |
| T0.4 | PASS | 5 deltas exact | (same) |
| T0.5 | PASS | R^2=0.102, 5e-11 | (same) |
| T0.6 | PASS | 8 folds exact | (same) |
| T1.1 | PASS | rebuilt fresh | src-identical (new IDs) |
| T1.2 | PASS | 1.18295343 | bit-identical (0.00) |
| T1.3 | PASS | smoke ok | identical to run1 |
| T2.1 | PARTIAL | =thesis LogLik/microerg | FULL TRACE bit-identical |
| T3.1a | PARTIAL | =run1 vs thesis | FULL TRACE identical |
| T3.1b | PARTIAL | =run1 vs thesis | FULL TRACE identical |
| T3.1c | PARTIAL | =run1 vs thesis | FULL TRACE identical |
| T3.2a | PASS | 3.79e-12 vs orig | 0.00 vs run1 |
| T3.2b | PASS | 5e-11 vs orig | 0.00 vs run1 |
| T3.2c | PASS* | 1e-6 (theta round) | 0.00 vs run1 |
| T3.3a | PASS | RMSE 0.344 | 0.00 vs run1 |
| T3.3b | PASS | RMSE 0.341 | 0.00 vs run1 |
| T3.3c | PASS | RMSE 0.420 | 0.00 vs run1 |
| T3.4 | PASS | 6/7 figures | (regen) |
| T4.1 | PARTIAL | =run1 vs thesis | FULL TRACE identical |
| T4.2 | PASS | 4.56e-12 vs orig | 0.00 vs run1 |

## Detailed Results

### Tier 0 (run2): all PASS, bit-identical to RUN 1
- T0.1 pytest 68 passed. T0.2 all 7 MD5 match.
- T0.3: delta 0.05 (5401/0.6044) & 0.02 (16922/0.6130); order-indep diff vs original = 0.00e+00 AND vs RUN 1 = 0.00e+00.
- T0.4: 0.005=67880/0.645, 0.01=36025/0.624, 0.02=16922/0.613, 0.05=5401/0.604, 0.1=2074/0.604 (all exact).
- T0.5: R^2=0.102338, coeff max diff 5.00e-11.
- T0.6: 8 folds, sizes+data identical.

### Tier 1 (run2)
- T1.1: rebuilt cpu=8af7666736a1, r=fe7c7077e814 (IDs differ from run1 only because build context now includes run1 results/; src/inst unchanged). PASS.
- **FINDING (root cause of the predict.R clobber, both runs)**: `preprocessing/tests/test_driver_cli.py` creates a dummy file named `predict.R` in a tmpdir and runs RPredictor with it; RPredictor (exageostat_driver.py:329-331) stages its script by `shutil.copy2(self.r_script, data_dir/self.r_script.name)` → copies the dummy onto the tracked `data/predict.R`. So **running pytest (T0.1) overwrites the real data/predict.R with '# dummy'** every time. Canonical source is `preprocessing/predict.R` (248 lines); `data/predict.R` is a staged copy. Restored via `git checkout HEAD -- data/predict.R`. The plan's T1.2 guard already protects subsequent machines (pytest runs only once, before T1.2). RECOMMEND fixing the test to not write into the tracked data/ dir (use an isolated cwd/tmp data dir).
- T1.2: pred(0.25,0.25)=1.18295342815 (diff 4.28e-7), consistent across N_test; **bit-identical to run1 (0.00)**. PASS.
- T1.3: smoke 5 iters, LogLik -6180.348488, #Found Maximum Theta present; Model Parameters lines identical to run1. PASS.

### Tier 2 (run2): T2.1 byte-identical to RUN 1
409 iter, sigma2=4.74302585, beta=14.57648197, nu=0.45072307, tau2=0.001,
LogLik=1100.932054. The ENTIRE iteration trace (every Model Parameters line) is
byte-identical to RUN 1. Same PARTIAL-vs-thesis verdict as run1 (LogLik+microergodic
reproduce, sigma2/beta on flat ridge). Confirms full optimizer-path determinism
across a fresh image rebuild.

### Tier 3 (run2)
- T3.2 predictions: all three bit-identical to RUN 1 (max diff 0.00e+00); same vs-original results as run1 (simple 3.79e-12, detrended 5e-11, indicator 1e-6 theta-rounding). PASS.
- T3.3 CV: weighted RMSE Simple=0.344, Universal=0.341, Indicator=0.420 (all match Tables 5.3/5.5). All 25 CV prediction files bit-identical to RUN 1 (0.00). PASS.
- T3.4: 6/7 figures regenerated (Fig 5.6 pending T4.2). PASS.

### Tier 3 (run2): T3.1 diagnostic MLEs byte-identical to RUN 1
nonugget (3.74198654,12.15674383,0.44086235; LL 1105.409401),
detrended (1.66545921,4.36908566,0.45497584,0.001; LL 1102.994002),
indicator (0.46589454,138.98353773,0.12578737,0.08718563; LL -2449.463760).
Full iteration traces identical to RUN 1. Same PARTIAL-vs-thesis verdict.

### Tier 4 (run2): byte-identical to RUN 1
- T4.1 delta=0.02 MLE: 259 iter, sigma2=2.62241120, beta=9.80219493, nu=0.39290767,
  tau2=0.001, LogLik=5854.140580. Full trace identical to RUN 1.
- T4.2 prediction: vs original pred 4.56e-12 / var 9.99e-15; vs RUN 1 = 0.00e+00. PASS.
- Fig 5.6 regenerated; all 7 figures present.

---

## FINAL VERDICT: RUN 2 (2026-06-09T16:26:17Z)

**Run 2 reproduces RUN 1 bit-for-bit at every step.** Determinism is total on this
machine, including across a fresh Docker image rebuild:
- Tier 0 preprocessing/CV folds: max diff 0.00e+00 vs run1 (and vs originals).
- T1.2 bug regression, T1.3 smoke: identical.
- ALL FIVE MLEs (baseline, no-nugget, detrended, indicator, delta=0.02): the
  ENTIRE iteration trace is byte-identical to RUN 1 (not just the final theta).
- All grid predictions + 25 CV fold predictions: max diff 0.00e+00 vs run1.
- CV tables: Simple 0.344, Universal 0.341, Indicator 0.420 (= Tables 5.3/5.5).
- All 7 figures regenerated.

vs THESIS: identical conclusion to run1, predictions/CV/figures reproduce exactly;
MLE (sigma2,beta,iter) deviate on the flat ridge while LogLik + microergodic
parameter reproduce.

**NEW in run 2**: root-caused the data/predict.R clobber, it is a pytest side
effect (test_driver_cli.py builds a dummy 'predict.R' and RPredictor copies it onto
the tracked data/predict.R). Not a mystery prior-session edit. Canonical source is
preprocessing/predict.R (248 lines). RECOMMEND fixing the test to use an isolated
data dir so pytest stops mutating the tracked file.
