"""Defense explainer figure for the logit transform.

Panel 1: logit(p) stretches [0,1] onto the whole real line.
Panel 2: expit (inverse) squashes the real line back into [0,1].
Panel 3: before/after on REAL delta=0.05 predictions -- native Kriging leaks
         outside [0,1]; logit Kriging cannot.
"""
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.special import expit, logit

OUT = "analysis"

# real predictions from the consolidated run
native, lgt = [], []
with open(f"{OUT}/predictions_delta005.csv") as f:
    r = csv.DictReader(f)
    for row in r:
        if row["method"] == "kriging_native":
            native.append(float(row["pred"]))
        elif row["method"] == "kriging_logit":
            lgt.append(float(row["pred"]))
native, lgt = np.array(native), np.array(lgt)
out_lo = (native < 0).sum()
out_hi = (native > 1).sum()
frac_out = 100 * (out_lo + out_hi) / len(native)

fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))

# Panel 1: logit
p = np.linspace(0.001, 0.999, 400)
ax[0].plot(p, logit(p), color="#4477aa", lw=2.5)
ax[0].axhline(0, color="gray", lw=.8); ax[0].axvline(0.5, color="gray", ls=":", lw=.8)
ax[0].plot(0.5, 0, "o", color="#ee6677", ms=9, zorder=5)
ax[0].annotate("p = 0.5  →  0", (0.5, 0), xytext=(0.55, -3.5), fontsize=11,
               arrowprops=dict(arrowstyle="->", color="#ee6677"))
ax[0].text(0.02, 5.2, "p → 1  pushes to +∞", fontsize=10, color="#666")
ax[0].text(0.02, -6.0, "p → 0  pushes to −∞", fontsize=10, color="#666")
ax[0].set(title="Step 1: logit stretches [0,1] onto the\nwhole number line",
          xlabel="proportion p  (connectivity)", ylabel="logit(p)",
          xlim=(0, 1), ylim=(-7, 7)); ax[0].grid(alpha=.3)

# Panel 2: expit (inverse) -- squash back, can never leave [0,1]
z = np.linspace(-7, 7, 400)
ax[1].plot(z, expit(z), color="#228833", lw=2.5)
ax[1].axhline(0, color="gray", lw=.8); ax[1].axhline(1, color="gray", lw=.8)
ax[1].fill_between(z, 0, 1, color="#228833", alpha=.05)
ax[1].text(-6.5, 0.9, "output is ALWAYS\nbetween 0 and 1", fontsize=10, color="#228833")
ax[1].set(title="Step 2: model on that scale, then squash\nback with the inverse (expit)",
          xlabel="value on logit scale", ylabel="back to proportion",
          xlim=(-7, 7), ylim=(-0.05, 1.05)); ax[1].grid(alpha=.3)

# Panel 3: real predictions, before vs after
bins = np.linspace(-0.45, 1.45, 40)
ax[2].hist(native, bins=bins, alpha=.6, color="#ee6677", label=f"native Kriging\n({frac_out:.1f}% leave [0,1])")
ax[2].hist(lgt, bins=bins, alpha=.6, color="#228833", label="logit Kriging\n(always in [0,1])")
ax[2].axvspan(-0.45, 0, color="red", alpha=.10); ax[2].axvspan(1, 1.45, color="red", alpha=.10)
ax[2].axvline(0, color="k", ls="--", lw=1); ax[2].axvline(1, color="k", ls="--", lw=1)
ax[2].text(-0.43, ax[2].get_ylim()[1]*0.6, "invalid\n(<0)", fontsize=9, color="red")
ax[2].text(1.02, ax[2].get_ylim()[1]*0.6, "invalid\n(>1)", fontsize=9, color="red")
ax[2].set(title="Real δ=0.05 predictions:\nnative leaks out, logit stays valid",
          xlabel="predicted connectivity probability", ylabel="count"); ax[2].legend(fontsize=9)

fig.tight_layout(); fig.savefig(f"{OUT}/logit_explainer.png", dpi=140)
print(f"native preds: n={len(native)}  below 0: {out_lo}  above 1: {out_hi}  "
      f"({frac_out:.1f}% invalid)  range=[{native.min():.3f},{native.max():.3f}]")
print(f"logit preds:  range=[{lgt.min():.3f},{lgt.max():.3f}]  (all valid)")
print(f"saved {OUT}/logit_explainer.png")
