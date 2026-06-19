# ExaGeoStatCPP Docker Image (CPU + R interface)
# Extends the base CPU image with R support for prediction via predict_data().
#
# PREREQUISITE: Build the CPU image first:
#   DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t exageostatcpp:cpu .
#
# Build:
#   DOCKER_BUILDKIT=1 docker build -f Dockerfile.r --platform linux/amd64 -t exageostatcpp:r .
#
# Usage (run R script inside container):
#   docker run --rm --platform linux/amd64 \
#     -v $(pwd)/data:/app/data \
#     -v $(pwd)/results:/app/results \
#     exageostatcpp:r Rscript /app/data/predict.R

# syntax=docker/dockerfile:1
FROM exageostatcpp:cpu AS base

LABEL maintainer="TCC Project"
LABEL description="ExaGeoStatCPP with R interface for Kriging prediction"
LABEL version="1.1.0-r"

ENV DEBIAN_FRONTEND=noninteractive

# Install R on top of the CPU image (everything else is already built)
RUN apt-get update && apt-get install -y \
    r-base \
    r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Install R dependencies (MASS may fail on older R; that's OK, it's not strictly needed)
RUN Rscript -e 'install.packages(c("Rcpp", "assertthat"), repos="https://cloud.r-project.org")'

WORKDIR /app/ExaGeoStatCPP

# Apply fixes before building:
# 1. R adapter: ProblemSize must include both train and test data
#    so that CalculateZObsNumber() returns the full training set size.
# 2. Kernel: UnivariateMaternNuggetsStationary had swapped i0/j0 indices
#    in CalculateDistance, transposing cross-covariance matrices (C12).
COPY src/Rcpp-adapters/FunctionsAdapter.cpp src/Rcpp-adapters/FunctionsAdapter.cpp
COPY src/kernels/concrete/UnivariateMaternNuggetsStationary.cpp src/kernels/concrete/UnivariateMaternNuggetsStationary.cpp

# Build the shared library for R.
# configure -r builds ExaGeoStatCPP, copies libExaGeoStatCPP.so to src/ExaGeoStatCPP.so,
# then WIPES bin/. So we rebuild bin/ after.
RUN ./configure -e -m -r

# Rebuild CLI binary (configure -r wiped bin/)
RUN ./configure -e -m && \
    cd bin && \
    cmake --build . -j $(nproc)

# Register dependency libraries so R can find them at runtime
RUN echo "/app/ExaGeoStatCPP/installdir/_deps/CHAMELEON/lib" > /etc/ld.so.conf.d/exageostat.conf && \
    echo "/app/ExaGeoStatCPP/installdir/_deps/STARPU/lib" >> /etc/ld.so.conf.d/exageostat.conf && \
    echo "/app/ExaGeoStatCPP/installdir/_deps/HWLOC/lib" >> /etc/ld.so.conf.d/exageostat.conf && \
    echo "/app/ExaGeoStatCPP/installdir/_deps/GSL/lib" >> /etc/ld.so.conf.d/exageostat.conf && \
    echo "/app/ExaGeoStatCPP/installdir/_deps/NLOPT/lib" >> /etc/ld.so.conf.d/exageostat.conf && \
    ldconfig

# Install the R package (--no-test-load because dyn.load needs LD_PRELOAD for MPI)
RUN R CMD INSTALL . --configure-args="-r" --no-test-load

# Replace R's rebuilt .so with the original one (has proper MPI/StarPU linking)
RUN cp /app/ExaGeoStatCPP/src/ExaGeoStatCPP.so \
       /usr/local/lib/R/site-library/ExaGeoStatCPP/libs/ExaGeoStatCPP.so

# LD_PRELOAD required for R to load ExaGeoStatCPP (MPI symbols not directly linked in .so)
ENV LD_PRELOAD="/lib/x86_64-linux-gnu/libmpi.so.40 /app/ExaGeoStatCPP/installdir/_deps/STARPU/lib/libstarpumpi-1.3.so.3"
ENV PATH=/app/ExaGeoStatCPP/bin:${PATH}

# Verify R package loads
RUN Rscript -e 'library(ExaGeoStatCPP); cat("ExaGeoStatCPP R package: OK\n")'

WORKDIR /app/ExaGeoStatCPP/bin

# Default: drop into R
CMD ["R"]
