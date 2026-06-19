"""Driver for invoking ExaGeoStatCPP via subprocess or Docker."""

import csv
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ExaGeoStatConfig:
    """Configuration for an ExaGeoStatCPP run.

    Attributes:
        data_path: Path to the input CSV (x,y,measurement format).
        kernel: Kernel name (e.g., univariate_matern_nuggets_stationary).
        dimension: Spatial dimension (2D, 3D, ST).
        dts: Dense tile size.
        computation: Computation mode (dense, tlr, dst).
        precision: Floating point precision (single, double).
        cores: Number of CPU cores.
        gpus: Number of GPUs.
        itheta: Initial theta parameters (colon-separated).
        olb: Optimization lower bounds (colon-separated).
        oub: Optimization upper bounds (colon-separated).
        zmiss: Number of missing observations for prediction.
        n: Problem size (auto-detected from CSV if None).
        verbose: Verbosity level (quiet, standard, detailed).
        extra_args: Additional CLI arguments.
    """

    data_path: Path = Path("preprocessing/output/aggregated_cells.csv")
    kernel: str = "univariate_matern_nuggets_stationary"
    dimension: str = "2D"
    dts: int = 320
    computation: str = "dense"
    precision: str = "double"
    cores: int = 4
    gpus: int = 0
    itheta: str = "1:0.1:0.5:0.1"
    olb: str = "0.01:0.01:0.01:0.01"
    oub: str = "5:500:5:1"
    zmiss: int = 0
    n: Optional[int] = None
    verbose: str = "standard"
    extra_args: list = field(default_factory=list)


class ExaGeoStatDriver:
    """Orchestrates ExaGeoStatCPP execution and result parsing.

    Docker layout (from Dockerfile/entrypoint):
      - Binary: /app/ExaGeoStatCPP/bin/examples/end-to-end/Example_Data_Generation_Modeling_and_Prediction
      - Entrypoint "example" command invokes that binary.
      - Data mount: host ./data → container /app/data
      - Logs mount: host ./logs → container /app/logs
      - Working dir inside container: /app/ExaGeoStatCPP/bin

    To pass a CSV, place it under ./data/ on host and reference /app/data/<file> in --data_path.
    """

    # Binary name inside the Docker container
    DOCKER_BINARY = (
        "./examples/end-to-end/"
        "Example_Data_Generation_Modeling_and_Prediction"
    )

    def __init__(
        self,
        config: ExaGeoStatConfig,
        binary_path: Optional[Path] = None,
        use_docker: bool = True,
        docker_image: str = "exageostatcpp:cpu",
    ):
        self.config = config
        self.binary_path = binary_path or Path(
            "bin/examples/end-to-end/"
            "Example_Data_Generation_Modeling_and_Prediction"
        )
        self.use_docker = use_docker
        self.docker_image = docker_image

    def _count_csv_rows(self) -> int:
        """Count rows in the input CSV (no header expected)."""
        with open(self.config.data_path) as f:
            return sum(1 for _ in f)

    def build_cli_args(self, data_path_override: Optional[str] = None) -> list[str]:
        """Build the ExaGeoStatCPP command-line arguments.

        Args:
            data_path_override: If set, use this path for --data_path instead
                of config.data_path. Useful for Docker where the container
                path differs from the host path.
        """
        cfg = self.config

        n = cfg.n or self._count_csv_rows()
        data_path = data_path_override or str(cfg.data_path)

        args = [
            f"--N={n}",
            f"--kernel={cfg.kernel}",
            f"--dimension={cfg.dimension}",
            f"--dts={cfg.dts}",
            f"--computation={cfg.computation}",
            f"--precision={cfg.precision}",
            f"--cores={cfg.cores}",
            f"--gpus={cfg.gpus}",
            f"--data_path={data_path}",
            f"--verbose={cfg.verbose}",
        ]

        if cfg.itheta:
            args.append(f"--itheta={cfg.itheta}")
        if cfg.olb:
            args.append(f"--olb={cfg.olb}")
        if cfg.oub:
            args.append(f"--oub={cfg.oub}")
        if cfg.zmiss > 0:
            args.append(f"--Zmiss={cfg.zmiss}")

        args.extend(cfg.extra_args)
        return args

    def _prepare_docker_data(self) -> tuple[Path, str]:
        """Copy data CSV to ./data/ for Docker mount and return container path.

        Returns (host_data_dir, container_data_path).
        """
        import shutil

        host_data_dir = Path.cwd() / "data"
        host_data_dir.mkdir(exist_ok=True)

        src = self.config.data_path
        dst = host_data_dir / src.name
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)

        container_path = f"/app/data/{src.name}"
        return host_data_dir, container_path

    def build_command(self) -> list[str]:
        """Build the full command (binary or Docker)."""
        if self.use_docker:
            host_data_dir, container_data_path = self._prepare_docker_data()
            cli_args = self.build_cli_args(data_path_override=container_data_path)

            cmd = [
                "docker", "run", "--rm",
                "--platform", "linux/amd64",
                "-v", f"{host_data_dir}:/app/data",
                "-v", f"{Path.cwd() / 'logs'}:/app/logs",
                "-v", f"{Path.cwd() / 'results'}:/app/results",
                self.docker_image,
                self.DOCKER_BINARY,
            ]
            cmd.extend(cli_args)
        else:
            cli_args = self.build_cli_args()
            cmd = [str(self.binary_path)]
            cmd.extend(cli_args)

        return cmd

    def run(self, capture_output: bool = True) -> "ExaGeoStatResult":
        """Execute ExaGeoStatCPP and parse the output."""
        cmd = self.build_command()

        t0 = time.monotonic()
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=3600,
        )
        elapsed = time.monotonic() - t0

        return ExaGeoStatResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=cmd,
            elapsed_seconds=elapsed,
        )


@dataclass
class ExaGeoStatResult:
    """Parsed result from an ExaGeoStatCPP execution."""

    returncode: int
    stdout: str
    stderr: str
    command: list[str]
    elapsed_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.returncode == 0

    def parse_estimated_theta(self) -> Optional[list[float]]:
        """Extract estimated theta parameters from stdout.

        Actual output format:
          #Found Maximum Theta at: 1.62895759 98.44626301 0.42827802
        Or:
          --> Final Theta Values (1.628958, 98.446263, 0.428278)
        """
        # Try the summary format first
        match = re.search(
            r"#Found Maximum Theta at:\s*([\d.e+-]+(?:\s+[\d.e+-]+)*)",
            self.stdout,
        )
        if match:
            return [float(v) for v in match.group(1).split()]

        # Fallback: final theta line
        match = re.search(
            r"Final Theta Values\s*\(([\d.,\s e+-]+)\)", self.stdout
        )
        if match:
            return [float(v.strip()) for v in match.group(1).split(",")]
        return None

    def parse_log_likelihood(self) -> Optional[float]:
        """Extract the final log-likelihood value.

        Actual output: #Final Log Likelihood value: 125.441848
        """
        match = re.search(
            r"#Final Log Likelihood value:\s*([-\d.e+]+)", self.stdout
        )
        if match:
            return float(match.group(1))
        return None

    def parse_n_iterations(self) -> Optional[int]:
        """Extract number of MLE iterations.

        Actual output: #Number of MLE Iterations: 33
        """
        match = re.search(
            r"#Number of MLE Iterations:\s*(\d+)", self.stdout
        )
        if match:
            return int(match.group(1))
        return None

    def parse_iteration_log(self) -> list[tuple[int, list[float], float]]:
        """Extract per-iteration theta and log-likelihood values.

        Actual output per iteration:
          16 - Model Parameters (1.602955, 98.914556, 0.418821)----> LogLi: 125.09...

        Returns list of (iteration, theta_values, log_likelihood).
        """
        pattern = re.compile(
            r"(\d+)\s*-\s*Model Parameters\s*\(([\d.,\s e+-]+)\)"
            r"\s*-+>\s*LogLi:\s*([-\d.e+]+)"
        )
        results = []
        for match in pattern.finditer(self.stdout):
            it = int(match.group(1))
            theta = [float(v.strip()) for v in match.group(2).split(",")]
            logli = float(match.group(3))
            results.append((it, theta, logli))
        return results


class RPredictor:
    """Run Kriging prediction via ExaGeoStatCPP's R interface in Docker.

    Uses predict.R which calls predict_data() from the ExaGeoStatCPP R package.
    This gives us actual predicted values (unlike the CLI which only stores them
    internally).
    """

    def __init__(
        self,
        docker_image: str = "exageostatcpp:r",
        r_script: Path = Path("preprocessing/predict.R"),
    ):
        self.docker_image = docker_image
        self.r_script = r_script

    def build_command(
        self,
        train_csv: Path,
        theta: list[float],
        output_csv: Path,
        kernel: str = "univariate_matern_nuggets_stationary",
        grid_res: int = 100,
        dts: int = 320,
        cores: int = 1,
        test_csv: Optional[Path] = None,
    ) -> list[str]:
        """Build Docker command for R prediction.

        Args:
            train_csv: Path to training data CSV (x, y, measurement).
            theta: Estimated theta parameters from MLE.
            output_csv: Path where predictions will be written.
            kernel: Kernel name.
            grid_res: Grid resolution per axis (ignored if test_csv provided).
            dts: Dense tile size.
            cores: Number of CPU cores. Default 1 to avoid GSL crashes
                under x86_64 emulation (StarPU parallelism + Bessel function).
            test_csv: Optional test locations CSV (x, y). If None, uses grid.
        """
        import shutil

        # Prepare host directories for Docker mounts
        data_dir = Path.cwd() / "data"
        results_dir = Path.cwd() / "results"
        data_dir.mkdir(exist_ok=True)
        results_dir.mkdir(exist_ok=True)

        # Copy train CSV to data dir
        train_dst = data_dir / train_csv.name
        if train_csv.resolve() != train_dst.resolve():
            shutil.copy2(train_csv, train_dst)

        # Copy R script to data dir
        r_dst = data_dir / self.r_script.name
        if self.r_script.resolve() != r_dst.resolve():
            shutil.copy2(self.r_script, r_dst)

        # Build theta string (colon-separated)
        theta_str = ":".join(str(t) for t in theta)

        # Docker command
        cmd = [
            "docker", "run", "--rm",
            "--platform", "linux/amd64",
            "-v", f"{data_dir}:/app/data",
            "-v", f"{results_dir}:/app/results",
            self.docker_image,
            "Rscript", f"/app/data/{self.r_script.name}",
            "--train", f"/app/data/{train_csv.name}",
            "--theta", theta_str,
            "--kernel", kernel,
            "--grid-res", str(grid_res),
            "--output", f"/app/results/{output_csv.name}",
            "--dts", str(dts),
            "--cores", str(cores),
        ]

        # Optional test locations
        if test_csv is not None:
            test_dst = data_dir / test_csv.name
            if test_csv.resolve() != test_dst.resolve():
                shutil.copy2(test_csv, test_dst)
            cmd.extend(["--test", f"/app/data/{test_csv.name}"])

        return cmd

    def run(
        self,
        train_csv: Path,
        theta: list[float],
        output_csv: Path,
        kernel: str = "univariate_matern_nuggets_stationary",
        grid_res: int = 100,
        dts: int = 320,
        cores: int = 1,
        test_csv: Optional[Path] = None,
        timeout: int = 3600,
    ) -> "RPredictionResult":
        """Execute R prediction and return results."""
        cmd = self.build_command(
            train_csv=train_csv,
            theta=theta,
            output_csv=output_csv,
            kernel=kernel,
            grid_res=grid_res,
            dts=dts,
            cores=cores,
            test_csv=test_csv,
        )

        t0 = time.monotonic()
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        elapsed = time.monotonic() - t0

        # Read predictions from output file
        results_dir = Path.cwd() / "results"
        pred_path = results_dir / output_csv.name
        predictions = None
        if result.returncode == 0 and pred_path.exists():
            import numpy as np
            try:
                predictions = np.genfromtxt(pred_path, delimiter=",")
                if np.any(np.isnan(predictions)):
                    predictions = None  # NaN means predict_data() failed
            except (ValueError, OSError):
                predictions = None

        return RPredictionResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            command=cmd,
            predictions=predictions,
            output_path=pred_path if pred_path.exists() else None,
            elapsed_seconds=elapsed,
        )


@dataclass
class RPredictionResult:
    """Result from an R prediction run."""

    returncode: int
    stdout: str
    stderr: str
    command: list[str]
    predictions: Optional[object] = None  # numpy array (x, y, pred)
    output_path: Optional[Path] = None
    elapsed_seconds: float = 0.0

    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.predictions is not None

    @property
    def n_predictions(self) -> int:
        if self.predictions is None:
            return 0
        return len(self.predictions)


def prepare_train_test_csvs(
    full_csv: Path,
    train_csv: Path,
    test_csv: Path,
    test_fraction: float = 0.2,
    seed: int = 42,
) -> tuple[int, int]:
    """Split a CSV into train and test sets.

    Returns (n_train, n_test).
    """
    import numpy as np

    rng = np.random.default_rng(seed)

    rows = []
    with open(full_csv) as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    n = len(rows)
    indices = rng.permutation(n)
    n_test = int(n * test_fraction)
    test_idx = set(indices[:n_test])

    train_csv.parent.mkdir(parents=True, exist_ok=True)
    test_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(train_csv, "w", newline="") as tf, open(
        test_csv, "w", newline=""
    ) as vf:
        tw = csv.writer(tf)
        vw = csv.writer(vf)
        for i, row in enumerate(rows):
            if i in test_idx:
                vw.writerow(row)
            else:
                tw.writerow(row)

    return n - n_test, n_test
