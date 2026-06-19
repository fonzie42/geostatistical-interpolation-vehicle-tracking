# ExaGeoStatCPP Docker Image (CPU-only)
# Uses BuildKit cache mounts to persist compiled dependencies across builds.
#
# Build (REQUIRES BuildKit):
#   DOCKER_BUILDKIT=1 docker build -t exageostatcpp:cpu .
#   DOCKER_BUILDKIT=1 docker build --platform linux/amd64 -t exageostatcpp:cpu .  # Apple Silicon
#
# First build: ~30min (deps compiled from source, then cached)
# Subsequent builds (source-only changes): ~5-8min (deps restored from cache)
#
# To force full dep rebuild (e.g. after cmake/ version bump):
#   DOCKER_BUILDKIT=1 docker build --no-cache -t exageostatcpp:cpu .

# syntax=docker/dockerfile:1
FROM ubuntu:22.04

LABEL maintainer="ExaGeoStatCPP Team"
LABEL description="ExaGeoStatCPP - Parallel High-Performance Geostatistics Framework (CPU-only)"
LABEL version="1.1.0"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies (cached as Docker layer)
RUN apt-get update && apt-get install -y \
    # Build essentials
    build-essential \
    cmake \
    autoconf \
    automake \
    libtool \
    libtool-bin \
    pkg-config \
    git \
    wget \
    curl \
    ca-certificates \
    # MPI support
    openmpi-bin \
    openmpi-common \
    libopenmpi-dev \
    # BLAS/LAPACK libraries
    libopenblas-dev \
    liblapack-dev \
    liblapacke-dev \
    # Additional dependencies
    gfortran \
    libgfortran5 \
    libhwloc-dev \
    libgsl-dev \
    python3 \
    # Utilities
    vim \
    less \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app/ExaGeoStatCPP

# Copy source code
COPY . .

# Configure and build ExaGeoStatCPP.
# BuildKit cache mount persists installdir/_deps/ across builds so that
# expensive dependencies (StarPU, Chameleon, NLOPT, etc.) are compiled once.
# On subsequent builds, cmake's find_package() finds them via PKG_CONFIG_PATH
# and skips recompilation entirely.
RUN --mount=type=cache,id=exageostat-deps,target=/tmp/deps-cache \
    set -e && \
    # Restore cached deps if available
    if [ -d /tmp/deps-cache/CHAMELEON ]; then \
        echo ">>> Restoring cached dependencies..." && \
        mkdir -p installdir/_deps && \
        cp -a /tmp/deps-cache/* installdir/_deps/ ; \
    fi && \
    # Set PKG_CONFIG_PATH so cmake finds pre-built deps
    export PKG_CONFIG_PATH="$PWD/installdir/_deps/CHAMELEON/lib/pkgconfig:$PWD/installdir/_deps/STARPU/lib/pkgconfig:$PWD/installdir/_deps/HWLOC/lib/pkgconfig:$PWD/installdir/_deps/GSL/lib/pkgconfig:$PWD/installdir/_deps/NLOPT/lib/pkgconfig:${PKG_CONFIG_PATH:-}" && \
    # Configure (finds cached deps or builds from source)
    ./configure -e -t -m && \
    cd bin && \
    cmake --build . -j $(nproc) && \
    cd .. && \
    # Save deps to cache for next build
    if [ -d installdir/_deps ]; then \
        echo ">>> Saving dependencies to cache..." && \
        cp -a installdir/_deps/* /tmp/deps-cache/ ; \
    fi

# Initialize environment variables (prevents undefined variable warnings)
ENV PKG_CONFIG_PATH=""
ENV LD_LIBRARY_PATH=""

# Set up environment variables for dependencies
ENV PKG_CONFIG_PATH=/app/ExaGeoStatCPP/installdir/_deps/CHAMELEON/lib/pkgconfig:${PKG_CONFIG_PATH}
ENV PKG_CONFIG_PATH=/app/ExaGeoStatCPP/installdir/_deps/STARPU/lib/pkgconfig:${PKG_CONFIG_PATH}
ENV PKG_CONFIG_PATH=/app/ExaGeoStatCPP/installdir/_deps/HWLOC/lib/pkgconfig:${PKG_CONFIG_PATH}
ENV PKG_CONFIG_PATH=/app/ExaGeoStatCPP/installdir/_deps/GSL/lib/pkgconfig:${PKG_CONFIG_PATH}
ENV PKG_CONFIG_PATH=/app/ExaGeoStatCPP/installdir/_deps/NLOPT/lib/pkgconfig:${PKG_CONFIG_PATH}

# Add library paths
ENV LD_LIBRARY_PATH=/app/ExaGeoStatCPP/installdir/_deps/CHAMELEON/lib:${LD_LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/app/ExaGeoStatCPP/installdir/_deps/STARPU/lib:${LD_LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/app/ExaGeoStatCPP/installdir/_deps/HWLOC/lib:${LD_LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/app/ExaGeoStatCPP/installdir/_deps/GSL/lib:${LD_LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/app/ExaGeoStatCPP/installdir/_deps/NLOPT/lib:${LD_LIBRARY_PATH}
ENV LD_LIBRARY_PATH=/app/ExaGeoStatCPP/bin/src:${LD_LIBRARY_PATH}

# Add binary path
ENV PATH=/app/ExaGeoStatCPP/bin:${PATH}
ENV PATH=/app/ExaGeoStatCPP/bin/examples/end-to-end:${PATH}

# Set working directory to bin for running tests and examples
WORKDIR /app/ExaGeoStatCPP/bin

# Copy entrypoint script
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

# Default command: show help
CMD ["help"]
