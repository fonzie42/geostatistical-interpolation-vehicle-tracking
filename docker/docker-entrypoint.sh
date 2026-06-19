#!/bin/bash
set -e

# ExaGeoStatCPP Docker Entrypoint Script
# This script initializes the container environment and handles various execution modes

# Color output helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}ExaGeoStatCPP Container${NC}"
echo -e "${GREEN}======================================${NC}"

# Display system information
echo -e "${BLUE}System Information:${NC}"
echo "  Working Directory: $(pwd)"
echo "  Available CPU Cores: $(nproc)"
echo "  Total Memory: $(free -h | awk '/^Mem:/ {print $2}')"

# Check for GPU support
if command -v nvidia-smi &> /dev/null; then
    echo -e "${GREEN}  GPU Support: Enabled${NC}"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | while IFS=',' read -r name driver memory; do
        echo "    - $name (Driver: $driver, Memory: $memory)"
    done
else
    echo -e "${YELLOW}  GPU Support: Disabled (CPU-only mode)${NC}"
fi

echo -e "${GREEN}======================================${NC}"
echo ""

# Change to bin directory (where built binaries are located)
cd /app/ExaGeoStatCPP/bin

# If no arguments provided, show usage and start interactive shell
if [ $# -eq 0 ]; then
    echo -e "${BLUE}No command specified. Starting interactive shell.${NC}"
    echo ""
    echo -e "${YELLOW}Quick Start Examples:${NC}"
    echo "  1. Run basic example:"
    echo "     ./examples/end-to-end/Example_Data_Generation_Modeling_and_Prediction \\"
    echo "       --N=1000 --kernel=univariate_matern_stationary --dts=100"
    echo ""
    echo "  2. Run tests:"
    echo "     ctest"
    echo ""
    echo "  3. Run specific test:"
    echo "     ./tests/cpp-tests/exageostat-tests"
    echo ""
    echo "  4. List available examples:"
    echo "     ls -la examples/"
    echo ""
    echo -e "${GREEN}======================================${NC}"
    exec /bin/bash
fi

# Handle special commands
case "$1" in
    example|demo)
        echo -e "${BLUE}Running demonstration example...${NC}"
        shift
        if [ $# -eq 0 ]; then
            # Default example
            exec ./examples/end-to-end/Example_Data_Generation_Modeling_and_Prediction \
                --N=1000 \
                --kernel=univariate_matern_stationary \
                --dts=100 \
                --itheta=1:0.1:0.5 \
                --max_mle_iterations=3 \
                --tolerance=4 \
                --verbose=detailed
        else
            # Custom example parameters - inject required defaults if missing
            ARGS=("$@")

            # Check if required parameters are missing and add defaults
            if ! [[ " ${ARGS[@]} " =~ " --itheta=" ]]; then
                echo -e "${YELLOW}Note: --itheta not specified, using default: 1:0.1:0.5${NC}"
                ARGS+=("--itheta=1:0.1:0.5")
            fi

            if ! [[ " ${ARGS[@]} " =~ " --max_mle_iterations=" ]]; then
                echo -e "${YELLOW}Note: --max_mle_iterations not specified, using default: 3${NC}"
                ARGS+=("--max_mle_iterations=3")
            fi

            if ! [[ " ${ARGS[@]} " =~ " --tolerance=" ]]; then
                echo -e "${YELLOW}Note: --tolerance not specified, using default: 4${NC}"
                ARGS+=("--tolerance=4")
            fi

            exec ./examples/end-to-end/Example_Data_Generation_Modeling_and_Prediction "${ARGS[@]}"
        fi
        ;;

    test|tests)
        echo -e "${BLUE}Running tests...${NC}"
        shift
        if [ $# -eq 0 ]; then
            # Run all tests with verbose output
            exec ctest --output-on-failure --verbose
        else
            # Run specific tests
            exec ctest "$@"
        fi
        ;;

    test-binary)
        echo -e "${BLUE}Running test binary directly...${NC}"
        shift
        exec ./tests/cpp-tests/exageostat-tests "$@"
        ;;

    benchmark)
        echo -e "${BLUE}Running benchmarking script...${NC}"
        shift
        if [ -f /app/ExaGeoStatCPP/scripts/Benchmarking.sh ]; then
            exec bash /app/ExaGeoStatCPP/scripts/Benchmarking.sh "$@"
        else
            echo -e "${RED}Error: Benchmarking script not found${NC}"
            exit 1
        fi
        ;;

    shell|bash)
        echo -e "${BLUE}Starting interactive shell...${NC}"
        exec /bin/bash
        ;;

    help|--help|-h)
        echo -e "${YELLOW}ExaGeoStatCPP Docker Container Usage${NC}"
        echo ""
        echo "Usage: docker run [docker-options] exageostatcpp[:tag] [command] [arguments]"
        echo ""
        echo "Commands:"
        echo "  example [args]           Run demonstration example (default or custom args)"
        echo "  test [ctest-args]        Run tests using ctest"
        echo "  test-binary [args]       Run test binary directly"
        echo "  benchmark [args]         Run benchmarking script"
        echo "  shell                    Start interactive bash shell"
        echo "  help                     Show this help message"
        echo "  [custom-command]         Execute any custom command in /app/ExaGeoStatCPP/bin"
        echo ""
        echo "Examples:"
        echo "  # Run default example"
        echo "  docker run exageostatcpp:cpu example"
        echo ""
        echo "  # Run example with custom parameters"
        echo "  docker run exageostatcpp:cpu example --N=5000 --dts=320 --kernel=bivariate_matern_flexible"
        echo ""
        echo "  # Run tests"
        echo "  docker run exageostatcpp:cpu test"
        echo ""
        echo "  # Interactive mode"
        echo "  docker run -it exageostatcpp:cpu shell"
        echo ""
        echo "  # GPU example"
        echo "  docker run --gpus all exageostatcpp:gpu example --N=10000 --gpus=1"
        echo ""
        exit 0
        ;;

    *)
        # Execute custom command
        echo -e "${BLUE}Executing custom command: $@${NC}"
        exec "$@"
        ;;
esac
