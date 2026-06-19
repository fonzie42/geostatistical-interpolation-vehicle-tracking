"""Regenerate the reliability/PIT figure for the LOGIT model (the one used in the
thesis), reconstructing logit-scale (m, s) from the back-transformed predictions and
95% interval in predictions_delta005.csv. The previous figure was the native model."""
import csv, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import logit, expit
from scipy.stats import norm

EPS = 1e-6
clip = lambda x: min(max(x, EPS), 1 - EPS)

true, m, s = [], [], []
with open("analysis/predictions_delta005.csv") as f:
    for r in csv.DictReader(f):
        if r["method"] != "kriging_logit":
            continue
        try:
            p, lo, hi, t = (float(r["pred"]), float(r["lo95"]),
                            float(r["hi95"]), float(r["true"]))
        except ValueError:
            continue
        mi = logit(clip(p))
        si = (logit(clip(hi)) - logit(clip(lo))) / (2 * 1.959963985)
        if si <= 0:
            continue
        true.append(t); m.append(mi); s.append(si)
true, m, s = np.array(true), np.array(m), np.array(s)
n = len(true)

# PIT on the logit scale
pit = norm.cdf((logit(np.clip(true, EPS, 1 - EPS)) - m) / s)

# reliability: empirical coverage of central intervals at several nominal levels
levels = np.array([0.50, 0.60, 0.70, 0.80, 0.90, 0.95])
emp = []
for a in levels:
    z = norm.ppf(0.5 + a / 2)
    lo, hi = expit(m - z * s), expit(m + z * s)
    emp.append(np.mean((true >= lo) & (true <= hi)))
emp = np.array(emp)

print(f"n={n}")
for a, e in zip(levels, emp):
    print(f"  nominal {a:.2f} -> empirical {e:.3f}")

fig, ax = plt.subplots(1, 2, figsize=(13, 4.6))
ax[0].hist(pit, bins=20, color="#6699cc", edgecolor="white")
ax[0].axhline(n / 20, color="#cc3333", ls="--", label="uniform (calibrated)")
ax[0].set(title="PIT histogram (logit model)", xlabel="PIT value", ylabel="count")
ax[0].legend()
ax[1].plot([0, 1], [0, 1], "--", color="#cc3333", label="ideal")
ax[1].plot(levels, emp, "o-", color="#228833", label="observed")
ax[1].set(title="Reliability: nominal vs empirical coverage",
          xlabel="nominal", ylabel="empirical", xlim=(0, 1), ylim=(0, 1))
ax[1].legend(); ax[1].set_aspect("equal")
fig.tight_layout()
fig.savefig("results/reliability_logit.png", dpi=130)
print("saved results/reliability_logit.png")
