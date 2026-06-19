"""Task 8: distribution of events per cell at delta=0.05 and delta=0.02.

Re-aggregates the raw parquet (counts are dropped from the exported CSVs) to
recover per-cell event counts, then reports how many cells sit near the
min_events=30 CLT floor and plots the histogram. Defends (or qualifies) the
CLT justification: the mean is huge (~12k) but the tail matters.
"""
import polars as pl
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PARQUET = "auxiliary_documents/2017-2018-2019-2020.parquet"
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = -33.8, -27.0, -57.7, -49.5
MIN_EVENTS = 30


def counts_for(delta):
    lf = pl.scan_parquet(PARQUET).filter(
        pl.col("latitude").is_between(LAT_MIN, LAT_MAX)
        & pl.col("longitude").is_between(LON_MIN, LON_MAX)
    ).with_columns(
        ((pl.col("latitude") - LAT_MIN) / delta).floor().alias("ilat"),
        ((pl.col("longitude") - LON_MIN) / delta).floor().alias("ilon"),
    ).group_by("ilat", "ilon").agg(pl.len().alias("n"))
    n = lf.collect()["n"].to_numpy()
    return n[n >= MIN_EVENTS]  # apply the same inclusion threshold


fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
for j, delta in enumerate([0.05, 0.02]):
    n = counts_for(delta)
    pct = lambda thr: 100.0 * (n < thr).mean()
    print(f"=== delta={delta}: {len(n)} cells (>= {MIN_EVENTS} events) ===")
    print(f"  mean={n.mean():.0f}  median={np.median(n):.0f}  min={n.min()}  max={n.max()}")
    print(f"  cells < 100 events:  {(n<100).sum():>5} ({pct(100):.1f}%)")
    print(f"  cells < 500 events:  {(n<500).sum():>5} ({pct(500):.1f}%)")
    print(f"  cells < 1000 events: {(n<1000).sum():>5} ({pct(1000):.1f}%)")
    ax[j].hist(np.log10(n), bins=40, color="#4477aa", edgecolor="k", alpha=.8)
    ax[j].axvline(np.log10(MIN_EVENTS), color="r", ls="--", label=f"floor={MIN_EVENTS}")
    ax[j].axvline(np.log10(100), color="orange", ls=":", label="100 (CLT comfort)")
    ax[j].set(title=f"Events/cell (delta={delta}, n={len(n)})",
              xlabel="log10(events per cell)", ylabel="cells"); ax[j].legend()

fig.tight_layout(); fig.savefig("results/events_per_cell.png", dpi=130)
print("saved results/events_per_cell.png")
print("DONE")
