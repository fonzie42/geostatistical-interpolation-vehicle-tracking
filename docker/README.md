# Docker

These Dockerfiles build the **ExaGeoStatCPP framework** (the C++ engine that performs
Maximum Likelihood Estimation and Kriging). They do not build this companion repository;
they build the ExaGeoStatCPP source tree.

- Fork used for this thesis (build from here): <https://github.com/fonzie42/ExaGeoStatCPP>
- Official upstream project: <https://github.com/ecrc/ExaGeoStatCPP>

## Important: build context

All three expect their build context to be a **checkout of the ExaGeoStatCPP source tree**
(the fork above), not this companion repo. `Dockerfile` and `Dockerfile.gpu` end with
`COPY . .` to pull in the full C++ source; `Dockerfile.r` builds `FROM exageostatcpp:cpu`
and copies only the R-adapter sources on top. In that source repo these files live at the
repository root, which is why `docker-compose.yml` uses `context: .` with
`dockerfile: Dockerfile`.

To build, clone the fork, check out its root (these files already live there), and run the
commands from there:

```bash
git clone https://github.com/fonzie42/ExaGeoStatCPP.git
cd ExaGeoStatCPP
```

The copies in this directory are included for provenance and reference so the thesis
pipeline is fully documented in one place.

| File | Image | Purpose |
|------|-------|---------|
| `Dockerfile` | `exageostatcpp:cpu` | CPU-only build (StarPU, Chameleon, GSL, NLOPT from source). Used for the CLI MLE runs and as the base for the R image. |
| `Dockerfile.r` | `exageostatcpp:r` | `FROM exageostatcpp:cpu`; adds R + the ExaGeoStatCPP R package. Provides `predict_data()` for Kriging prediction. |
| `Dockerfile.gpu` | `exageostatcpp:gpu` | `FROM nvidia/cuda:11.8.0-devel-ubuntu22.04`. GPU build used for the MLE theta estimation (the `mle_*_gpu.log` logs). CUDA < 12 only. |
| `docker-compose.yml` | both | Service definitions with volume mounts (`./data`, `./logs`, `./results`) and resource limits. |
| `.dockerignore` | - | Excludes `bin/`, `installdir/`, build artifacts from the build context. |
| `docker-entrypoint.sh` | cpu/gpu | Container entrypoint: prints system info, then dispatches `help`, a shell, or an ExaGeoStatCPP CLI command. |

## Build (run from an ExaGeoStatCPP source checkout root)

```bash
# CPU image
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t exageostatcpp:cpu -f Dockerfile .

# R image (depends on the CPU image)
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t exageostatcpp:r -f Dockerfile.r .

# GPU image (needs an NVIDIA GPU + nvidia-docker, CUDA < 12)
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t exageostatcpp:gpu -f Dockerfile.gpu .
```

The first CPU build takes roughly 30 minutes because the numerical dependencies (StarPU,
Chameleon, HWLOC, GSL, NLOPT) compile from source during the CMake configure step.

## Run

```bash
# MLE parameter estimation (CLI). Mount this repo's data/logs/results.
docker run --rm --platform linux/amd64 \
  -v "$PWD/data:/app/data" -v "$PWD/logs:/app/logs" -v "$PWD/results:/app/results" \
  exageostatcpp:cpu \
  ./examples/end-to-end/DataGenerationModelingAndPrediction \
  --N=5401 --kernel=univariate_matern_nuggets_stationary --dts=320 \
  --data_path=/app/data/delta_0.05_utm.csv

# Kriging prediction via the R interface (returns predictions directly)
docker run --rm --platform linux/amd64 \
  -v "$PWD:/work" -w /work exageostatcpp:r \
  Rscript preprocessing/predict.R   # see preprocessing/predict.R for arguments
```

The CLI does **not** print or write predicted values (it keeps them in an in-memory
`Results` singleton); MLE theta is read from the log output. Prediction values come from
the R interface (`predict_data()` in `preprocessing/predict.R`). See the top-level
`README.md` for the full workflow.
