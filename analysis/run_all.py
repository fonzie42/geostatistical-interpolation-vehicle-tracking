"""Consolidated analysis. Reproducible single driver.

Re-aggregates per-cell counts from the parquet (so logit and CLT analyses have
real n,k), generates the 3x3 spatial-block folds in-code, and runs every method
on identical cells, saving PER-POINT predictions, aggregate metrics, reliability,
and figures into this folder.

Methods (delta=0.05 and delta=0.02):
  mean-only, IDW(p=2), native Kriging (theta_studio on proportions),
  logit Kriging (count-based Haldane logit, theta fit per resolution).

Outputs (analysis/):
  predictions_delta{005,002}.csv  long: resolution,fold,x,y,true,method,pred,sd,lo95,hi95
  metrics_summary.csv             method,resolution,n,rmse,mae,bias,cov50,cov80,cov90,cov95
  theta_estimates.csv             resolution,scale,sigma2,beta,nu,tau2
  reliability.png, variogram.png, events_per_cell.png
Run from repo root:  .venv/bin/python3 analysis/run_all.py
"""
import sys
import csv
import warnings
import numpy as np
import polars as pl

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
from preprocessing.kriging import matern_covariance, MaternParams, kriging_predict
from scipy.optimize import minimize
from scipy.spatial.distance import cdist
from scipy.special import expit
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "analysis"
PARQUET = "auxiliary_documents/2017-2018-2019-2020.parquet"
LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = -33.8, -27.0, -57.7, -49.5
MIN_EVENTS = 30
THETA_STUDIO = MaternParams(4.743, 14.58, 0.451, 0.001)  # canonical native-scale
NOM = [0.50, 0.80, 0.90, 0.95]
ZQ = {0.50: 0.674490, 0.80: 1.281552, 0.90: 1.644854, 0.95: 1.959964}


def aggregate(delta):
    lf = pl.scan_parquet(PARQUET).filter(
        pl.col("latitude").is_between(LAT_MIN, LAT_MAX)
        & pl.col("longitude").is_between(LON_MIN, LON_MAX)
    ).with_columns(
        ((pl.col("latitude") - LAT_MIN) / delta).floor().alias("ilat"),
        ((pl.col("longitude") - LON_MIN) / delta).floor().alias("ilon"),
        (pl.col("online") >= 1).cast(pl.Int64).alias("on"),
    ).group_by("ilat", "ilon").agg(
        pl.len().alias("n"), pl.col("on").sum().alias("k")
    ).filter(pl.col("n") >= MIN_EVENTS).with_columns(
        (LON_MIN + (pl.col("ilon") + 0.5) * delta).alias("x"),
        (LAT_MIN + (pl.col("ilat") + 0.5) * delta).alias("y"),
    )
    d = lf.collect().select("x", "y", "n", "k").to_numpy()
    return d[:, :2], d[:, 2], d[:, 3]  # xy, n, k


def block_ids(xy, nb=3):
    x, y = xy[:, 0], xy[:, 1]
    xe = np.linspace(x.min(), x.max(), nb + 1)
    ye = np.linspace(y.min(), y.max(), nb + 1)
    xb = np.clip(np.digitize(x, xe[1:-1]), 0, nb - 1)
    yb = np.clip(np.digitize(y, ye[1:-1]), 0, nb - 1)
    return yb * nb + xb


def idw(tl, tv, te, power=2):
    d = cdist(te, tl)
    out = np.empty(len(te))
    for i in range(len(te)):
        di = d[i]
        z = di == 0
        out[i] = tv[z].mean() if z.any() else (tv / di ** power).sum() / (1 / di ** power).sum()
    return out


def negll(prm, D, y):
    s2, beta, nu, t2 = prm
    if min(s2, beta, nu, t2) <= 0 or nu > 3 or beta > 200:
        return 1e12
    C = matern_covariance(D, MaternParams(s2, beta, nu, t2))
    C[np.diag_indices_from(C)] = s2 + t2
    try:
        L = np.linalg.cholesky(C + 1e-8 * np.eye(len(C)))
    except np.linalg.LinAlgError:
        return 1e12
    a = np.linalg.solve(L.T, np.linalg.solve(L, y))
    return 0.5 * (y @ a) + np.log(np.diag(L)).sum() + 0.5 * len(y) * np.log(2 * np.pi)


def fit_logit_theta(xy, yl, seed=0, sub=1800):
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(xy), size=min(sub, len(xy)), replace=False)
    D = cdist(xy[idx], xy[idx])
    res = minimize(negll, [yl.var(), 5.0, 0.5, 0.05], args=(D, yl[idx] - yl[idx].mean()),
                   method="Nelder-Mead", options={"maxiter": 500, "xatol": 1e-3, "fatol": 1e-2})
    return MaternParams(*res.x)


def metrics(pred, true):
    e = pred - true
    return np.sqrt((e ** 2).mean()), np.abs(e).mean(), e.mean()


def run_resolution(delta, pred_writer, summary, theta_rows):
    tag = f"{delta:.3f}".replace("0.0", "00").replace("0.", "0")
    xy, n, k = aggregate(delta)
    p = k / n
    yl = np.log((k + 0.5) / (n - k + 0.5))  # Haldane logit
    bid = block_ids(xy)
    theta_logit = fit_logit_theta(xy, yl)
    theta_rows.append([delta, "native", *[f"{v:.4f}" for v in
                       (THETA_STUDIO.sigma2, THETA_STUDIO.beta, THETA_STUDIO.nu, THETA_STUDIO.nugget)]])
    theta_rows.append([delta, "logit", *[f"{v:.4f}" for v in
                       (theta_logit.sigma2, theta_logit.beta, theta_logit.nu, theta_logit.nugget)]])
    print(f"\n##### delta={delta}  N={len(xy)}  logit theta: "
          f"s2={theta_logit.sigma2:.3f} beta={theta_logit.beta:.3f} "
          f"nu={theta_logit.nu:.3f} t2={theta_logit.nugget:.4f}", flush=True)

    acc = {m: {"n": 0, "rmse2N": 0, "maeN": 0, "biasN": 0,
               "cov": {q: [] for q in NOM}} for m in
           ["mean", "idw", "kriging_native", "kriging_logit"]}

    for b in sorted(set(bid.tolist())):
        te = bid == b
        nb = int(te.sum())
        if nb == 0:
            continue
        trxy, te_xy = xy[~te], xy[te]
        trp, tep = p[~te], p[te]
        tryl = yl[~te]
        preds = {}
        # mean / idw (no uncertainty)
        preds["mean"] = (np.full(nb, trp.mean()), None)
        preds["idw"] = (idw(trxy, trp, te_xy), None)
        # native kriging on proportions
        kp, kv, _ = kriging_predict(trxy, trp, te_xy, THETA_STUDIO)
        preds["kriging_native"] = (kp, np.sqrt(np.maximum(kv, 1e-12)))
        # logit kriging
        m0 = tryl.mean()
        lp, lv, _ = kriging_predict(trxy, tryl - m0, te_xy, theta_logit)
        lp = lp + m0
        lsd = np.sqrt(np.maximum(lv, 1e-12))
        preds["kriging_logit"] = (expit(lp), ("logit", lp, lsd))

        for m, (pred, unc) in preds.items():
            r, a, bi = metrics(pred, tep)
            A = acc[m]
            A["n"] += nb; A["rmse2N"] += nb * r * r; A["maeN"] += nb * a; A["biasN"] += nb * bi
            # per-point rows + coverage
            for q in NOM:
                if unc is None:
                    pass
                elif isinstance(unc, tuple):  # logit
                    _, lpv, lsdv = unc
                    lo, hi = expit(lpv - ZQ[q] * lsdv), expit(lpv + ZQ[q] * lsdv)
                    A["cov"][q].append((tep >= lo) & (tep <= hi))
                else:  # native sd
                    lo, hi = pred - ZQ[q] * unc, pred + ZQ[q] * unc
                    A["cov"][q].append((tep >= lo) & (tep <= hi))
            # write per-point (use 95% interval)
            for i in range(nb):
                if unc is None:
                    sd = lo = hi = ""
                elif isinstance(unc, tuple):
                    _, lpv, lsdv = unc
                    sd = f"{lsdv[i]:.5f}"; lo = f"{expit(lpv[i]-1.959964*lsdv[i]):.5f}"
                    hi = f"{expit(lpv[i]+1.959964*lsdv[i]):.5f}"
                else:
                    sd = f"{unc[i]:.5f}"; lo = f"{pred[i]-1.959964*unc[i]:.5f}"
                    hi = f"{pred[i]+1.959964*unc[i]:.5f}"
                pred_writer.writerow([delta, b, f"{te_xy[i,0]:.4f}", f"{te_xy[i,1]:.4f}",
                                      f"{tep[i]:.5f}", m, f"{pred[i]:.5f}", sd, lo, hi])

    for m, A in acc.items():
        N = A["n"]
        row = [m, delta, N, round((A["rmse2N"]/N)**.5, 4), round(A["maeN"]/N, 4),
               round(A["biasN"]/N, 4)]
        for q in NOM:
            row.append(round(np.concatenate(A["cov"][q]).mean()*100, 1) if A["cov"][q] else "")
        summary.append(row)
        print(f"  {m:>16}: RMSE={row[3]:.3f} MAE={row[4]:.3f} bias={row[5]:+.3f} "
              f"cov95={row[-1]}", flush=True)
    return acc, xy, n, k, p, yl


# ---- run ----
pf = open(f"{OUT}/predictions_delta005.csv", "w", newline="")
pw = csv.writer(pf); pw.writerow(["resolution","fold","x","y","true","method","pred","sd","lo95","hi95"])
summary, theta_rows = [], []
acc5, xy5, n5, k5, p5, yl5 = run_resolution(0.05, pw, summary, theta_rows)
pf.close()

pf2 = open(f"{OUT}/predictions_delta002.csv", "w", newline="")
pw2 = csv.writer(pf2); pw2.writerow(["resolution","fold","x","y","true","method","pred","sd","lo95","hi95"])
run_resolution(0.02, pw2, summary, theta_rows)
pf2.close()

with open(f"{OUT}/metrics_summary.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["method","resolution","n","rmse","mae","bias","cov50","cov80","cov90","cov95"])
    w.writerows(summary)
with open(f"{OUT}/theta_estimates.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["resolution","scale","sigma2","beta","nu","tau2"])
    w.writerows(theta_rows)

# ---- figures (delta=0.05) ----
# reliability: native vs logit
fig, ax = plt.subplots(figsize=(5.5, 5))
ax.plot([0,1],[0,1],"r--",label="ideal")
for m, c in [("kriging_native","#ee6677"),("kriging_logit","#228833")]:
    emp = [r[6+i] for r in summary if r[0]==m and r[1]==0.05][0:1]  # placeholder
row_n = [r for r in summary if r[0]=="kriging_native" and r[1]==0.05][0]
row_l = [r for r in summary if r[0]=="kriging_logit" and r[1]==0.05][0]
ax.plot(NOM, [row_n[6+i]/100 for i in range(4)], "o-", color="#ee6677", label="native Kriging")
ax.plot(NOM, [row_l[6+i]/100 for i in range(4)], "s-", color="#228833", label="logit Kriging")
ax.set(title="Reliability (delta=0.05): nominal vs empirical coverage",
       xlabel="nominal", ylabel="empirical"); ax.legend(); ax.grid(alpha=.3)
fig.tight_layout(); fig.savefig(f"{OUT}/reliability.png", dpi=130)

# events/cell
fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
for j,(dd,nn) in enumerate([(0.05,n5),(0.02,aggregate(0.02)[1])]):
    ax[j].hist(np.log10(nn), bins=40, color="#4477aa", edgecolor="k", alpha=.8)
    ax[j].axvline(np.log10(30), color="r", ls="--", label="floor=30")
    ax[j].axvline(np.log10(np.median(nn)), color="green", ls="-", label=f"median={int(np.median(nn))}")
    ax[j].set(title=f"Events/cell delta={dd} (n={len(nn)})", xlabel="log10(events)", ylabel="cells"); ax[j].legend()
fig.tight_layout(); fig.savefig(f"{OUT}/events_per_cell.png", dpi=130)

# variogram (delta=0.05)
rng = np.random.default_rng(42); idx = rng.choice(len(xy5), min(2500,len(xy5)), replace=False)
sx, sp = xy5[idx], p5[idx]
dx = sx[:,0][:,None]-sx[:,0][None,:]; dy = sx[:,1][:,None]-sx[:,1][None,:]
h = np.sqrt(dx**2+dy**2); g = 0.5*(sp[:,None]-sp[None,:])**2
ang = np.degrees(np.arctan2(dy,dx))%180
iu = np.triu_indices(len(sp),1); h,g,ang = h[iu],g[iu],ang[iu]
bins = np.linspace(0,4,21); bc=0.5*(bins[:-1]+bins[1:])
def binned(mask):
    o=np.full(len(bc),np.nan)
    for i in range(len(bc)):
        mm=mask&(h>=bins[i])&(h<bins[i+1])
        if mm.sum()>30: o[i]=g[mm].mean()
    return o
fig, ax = plt.subplots(1,2,figsize=(12,4.5))
hh=np.linspace(1e-3,4,200); model=(THETA_STUDIO.sigma2+THETA_STUDIO.nugget)-matern_covariance(hh,THETA_STUDIO)
ax[0].plot(bc,binned(np.ones_like(h,bool)),"o",color="#4477aa",label="empirical")
ax[0].plot(hh,model,"-",color="#ee6677",label="fitted Matern (native)")
ax[0].set(title="Variogram vs fitted model (native scale)",xlabel="h (deg)",ylabel="semivariance",ylim=(0,0.2)); ax[0].legend(); ax[0].grid(alpha=.3)
for nm,(a,bb) in {"0 E-W":(0,22.5),"45":(22.5,67.5),"90 N-S":(67.5,112.5),"135":(112.5,157.5)}.items():
    mm=(ang>=a)&(ang<bb) if nm!="0 E-W" else ((ang<22.5)|(ang>=157.5))
    ax[1].plot(bc,binned(mm),"o-",label=nm,alpha=.8)
ax[1].set(title="Directional variograms",xlabel="h (deg)",ylabel="semivariance"); ax[1].legend(); ax[1].grid(alpha=.3)
fig.tight_layout(); fig.savefig(f"{OUT}/variogram.png", dpi=130)

print("\n=== SAVED ===")
print("predictions_delta005.csv, predictions_delta002.csv, metrics_summary.csv,")
print("theta_estimates.csv, reliability.png, events_per_cell.png, variogram.png")
print("DONE", flush=True)
