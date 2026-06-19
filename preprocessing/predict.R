#!/usr/bin/env Rscript
# predict.R: Kriging prediction using ExaGeoStatCPP's R interface.
#
# Usage (inside Docker):
#   Rscript /app/data/predict.R \
#     --train /app/data/train.csv \
#     --theta "1.629:98.446:0.428:0.1" \
#     --kernel "univariate_matern_nuggets_stationary" \
#     --grid-res 100 \
#     --output /app/results/predictions.csv \
#     --dts 320
#
# Input:
#   --train: CSV file (no header) with columns: x, y, measurement
#   --theta: Colon-separated estimated theta parameters from MLE
#   --kernel: Kernel name (default: univariate_matern_nuggets_stationary)
#   --grid-res: Grid resolution per axis for prediction (default: 100)
#   --output: Output CSV path for predictions
#   --dts: Dense tile size (default: 320)
#   --test: (Optional) CSV file with test locations (x, y) instead of grid
#
# Output CSV: x, y, predicted_value, kriging_variance (no header)
#
# Kriging variances are computed in pure R after predict_data() returns,
# because ExaGeoStatCPP does not expose per-point variances.
# The variance formula is: var(s*) = C(s*,s*) - c(s*)' C22^{-1} c(s*)
# where C22 is the training covariance matrix and c(s*) is the cross-covariance.

library(ExaGeoStatCPP)

# Parse command line arguments
args <- commandArgs(trailingOnly = TRUE)

parse_args <- function(args) {
  params <- list(
    train = NULL,
    theta = NULL,
    kernel = "univariate_matern_nuggets_stationary",
    grid_res = 100,
    output = "predictions.csv",
    dts = 320,
    test = NULL,
    cores = 4
  )

  i <- 1
  while (i <= length(args)) {
    if (args[i] == "--train") {
      params$train <- args[i + 1]; i <- i + 2
    } else if (args[i] == "--theta") {
      params$theta <- args[i + 1]; i <- i + 2
    } else if (args[i] == "--kernel") {
      params$kernel <- args[i + 1]; i <- i + 2
    } else if (args[i] == "--grid-res") {
      params$grid_res <- as.integer(args[i + 1]); i <- i + 2
    } else if (args[i] == "--output") {
      params$output <- args[i + 1]; i <- i + 2
    } else if (args[i] == "--dts") {
      params$dts <- as.integer(args[i + 1]); i <- i + 2
    } else if (args[i] == "--test") {
      params$test <- args[i + 1]; i <- i + 2
    } else if (args[i] == "--cores") {
      params$cores <- as.integer(args[i + 1]); i <- i + 2
    } else {
      cat("Unknown argument:", args[i], "\n")
      i <- i + 1
    }
  }
  return(params)
}

params <- parse_args(args)

# Validate required arguments
if (is.null(params$train)) stop("--train is required")
if (is.null(params$theta)) stop("--theta is required")

# Read training data (no header: x, y, measurement)
cat("Reading training data:", params$train, "\n")
train_raw <- read.csv(params$train, header = FALSE)
colnames(train_raw) <- c("x", "y", "z")
cat("  Training points:", nrow(train_raw), "\n")

# Parse theta parameters
theta <- as.numeric(strsplit(params$theta, ":")[[1]])
cat("  Theta parameters:", theta, "\n")
cat("  Kernel:", params$kernel, "\n")

# Prepare test locations
if (!is.null(params$test)) {
  # User-provided test locations
  cat("Reading test locations:", params$test, "\n")
  test_raw <- read.csv(params$test, header = FALSE)
  test_x <- test_raw[, 1]
  test_y <- test_raw[, 2]
} else {
  # Generate regular prediction grid
  x_range <- range(train_raw$x)
  y_range <- range(train_raw$y)
  # Expand grid slightly beyond data extent
  margin <- 0.01
  x_seq <- seq(x_range[1] - margin, x_range[2] + margin, length.out = params$grid_res)
  y_seq <- seq(y_range[1] - margin, y_range[2] + margin, length.out = params$grid_res)
  grid <- expand.grid(x = x_seq, y = y_seq)
  test_x <- grid$x
  test_y <- grid$y
}
cat("  Prediction points:", length(test_x), "\n")

# Initialize ExaGeoStatCPP hardware
cat("Initializing ExaGeoStatCPP hardware...\n")
hardware <- new(Hardware, "exact", params$cores, 0, 1, 1)

# Run prediction
cat("Running Kriging prediction...\n")
predictions <- predict_data(
  kernel = params$kernel,
  estimated_theta = theta,
  dts = params$dts,
  train_data = list(train_raw$x, train_raw$y, train_raw$z),
  test_data = list(test_x, test_y),
  dimension = "2D"
)

# Finalize hardware
hardware$finalize_hardware()

# ============================================================
# Kriging variance computation (pure R)
# ============================================================
# ExaGeoStatCPP's predict_data() only returns predictions, not variances.
# We compute them here using the Matérn covariance function and Cholesky solve.
#
# For kernel "univariate_matern_nuggets_stationary":
#   theta = c(sigma2, beta, nu, nugget)
#   C(h) = sigma2 / (2^(nu-1) * gamma(nu)) * (h/beta)^nu * besselK(h/beta, nu)
#   C(0) = sigma2 + nugget
#
# For kernel "univariate_matern_stationary":
#   theta = c(sigma2, beta, nu)
#   Same formula, nugget = 0

cat("Computing Kriging variances in R...\n")

# Extract Matérn parameters from theta
sigma2 <- theta[1]
beta   <- theta[2]
nu     <- theta[3]
nugget <- if (length(theta) >= 4) theta[4] else 0.0

cat("  Matérn params: sigma2=", sigma2, " beta=", beta, " nu=", nu, " nugget=", nugget, "\n")

# Matérn covariance function (matches ExaGeoStatCPP's implementation exactly)
matern_cov <- function(h, sigma2, beta, nu, nugget) {
  result <- numeric(length(h))
  zero_mask <- (h == 0)
  result[zero_mask] <- sigma2 + nugget

  nz <- !zero_mask
  if (any(nz)) {
    scaled <- h[nz] / beta
    con <- sigma2 / (2^(nu - 1) * gamma(nu))
    result[nz] <- con * (scaled^nu) * besselK(scaled, nu)
  }
  # Preserve matrix dimensions (numeric() flattens to vector)
  if (is.matrix(h)) dim(result) <- dim(h)
  return(result)
}

# Euclidean distance between two sets of 2D points
# Returns matrix of size nrow(a) x nrow(b)
dist_matrix <- function(ax, ay, bx, by) {
  # Use outer products for vectorized computation
  dx <- outer(ax, bx, "-")
  dy <- outer(ay, by, "-")
  sqrt(dx^2 + dy^2)
}

n_train <- nrow(train_raw)
n_test  <- length(test_x)

cat("  Building C22 (", n_train, "x", n_train, ") ... ")
t_start <- proc.time()
D22 <- dist_matrix(train_raw$x, train_raw$y, train_raw$x, train_raw$y)
C22 <- matern_cov(D22, sigma2, beta, nu, nugget)
rm(D22)  # free memory
cat("done (", (proc.time() - t_start)[3], "s)\n")

cat("  Cholesky factorization of C22 ... ")
t_start <- proc.time()
L <- chol(C22)  # upper triangular: C22 = L' %*% L
rm(C22)  # free memory (~2.3 GB for N=17K)
cat("done (", (proc.time() - t_start)[3], "s)\n")

# Compute variances in batches to limit memory usage of C12
batch_size <- 500
variances <- numeric(n_test)

cat("  Computing variances (", n_test, " points, batch_size=", batch_size, ") ... \n")
t_start <- proc.time()

for (b_start in seq(1, n_test, by = batch_size)) {
  b_end <- min(b_start + batch_size - 1, n_test)
  batch_idx <- b_start:b_end

  # C12_batch: cross-covariance between test batch and training points
  # Dimensions: length(batch_idx) x n_train
  D12 <- dist_matrix(test_x[batch_idx], test_y[batch_idx], train_raw$x, train_raw$y)
  C12 <- matern_cov(D12, sigma2, beta, nu, nugget = 0)  # no nugget in cross-covariance
  rm(D12)

  # Solve L' %*% W = C12' for W, then var = C(0) - colSums(W^2)
  # C12 is (batch x n_train), we need to solve with L (upper tri, n_train x n_train)
  # backsolve(L, C12_t) solves L %*% W = C12_t
  C12_t <- t(C12)
  rm(C12)
  W <- backsolve(L, C12_t, transpose = TRUE)  # solves L' %*% W = C12_t
  rm(C12_t)

  variances[batch_idx] <- (sigma2 + nugget) - colSums(W^2)
  rm(W)

  if (b_start %% (batch_size * 10) == 1 || b_end == n_test) {
    cat("    Processed", b_end, "/", n_test, "points\n")
  }
}

elapsed <- (proc.time() - t_start)[3]
cat("  Done (", elapsed, "s)\n")

# Clamp negative variances to zero (numerical noise near training points)
n_negative <- sum(variances < 0)
if (n_negative > 0) {
  cat("  Warning:", n_negative, "negative variances clamped to 0 (numerical noise)\n")
  variances[variances < 0] <- 0
}

cat("  Variance range: [", min(variances), ",", max(variances), "]\n")

# Write output: x, y, predicted_value, kriging_variance
cat("Writing predictions to:", params$output, "\n")
output_df <- data.frame(x = test_x, y = test_y, prediction = predictions, variance = variances)
write.table(output_df, file = params$output, sep = ",",
            row.names = FALSE, col.names = FALSE)

cat("Done. Predictions:", length(predictions), "points\n")
cat("  Prediction range: [", min(predictions), ",", max(predictions), "]\n")
cat("  Variance range:   [", min(variances), ",", max(variances), "]\n")
