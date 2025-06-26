#!/bin/bash

# NS-3 Simulation Setup Script
# This script sets up and configures the NS-3 simulation environment

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
NS3_DIR="/opt/ns3"
SIMULATION_CONFIG="slicing-simulation.cc"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ns3-dir)
            NS3_DIR="$2"
            shift 2
            ;;
        --config)
            SIMULATION_CONFIG="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --ns3-dir DIR     Path to NS-3 installation (default: /opt/ns3)"
            echo "  --config FILE    Simulation configuration file (default: slicing-simulation.cc)"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== NS-3 Simulation Setup ===${NC}"
echo -e "NS-3 Directory: ${NS3_DIR}"
echo -e "Config File:    ${SIMULATION_CONFIG}"
echo ""

# Check if NS-3 directory exists
if [ ! -d "${NS3_DIR}" ]; then
    echo -e "${YELLOW}NS-3 directory not found at ${NS3_DIR}${NC}"
    echo -e "Please install NS-3 or specify the correct path with --ns3-dir"
    exit 1
fi

# Check if configuration file exists
if [ ! -f "${SIMULATION_CONFIG}" ]; then
    echo -e "${YELLOW}Configuration file not found: ${SIMULATION_CONFIG}${NC}"
    echo -e "Please specify the correct path with --config"
    exit 1
fi

# Copy configuration file to NS-3 scratch directory
cp "${SIMULATION_CONFIG}" "${NS3_DIR}/scratch/"

# Build the simulation
echo -e "${BLUE}Building NS-3 simulation...${NC}"
(
    cd "${NS3_DIR}" || exit 1
    ./waf clean
    ./waf configure --enable-examples --enable-tests
    ./waf build
)

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to build NS-3 simulation${NC}"
    exit 1
fi

# Get the base name of the configuration file (without .cc extension)
SIMULATION_NAME=$(basename "${SIMULATION_CONFIG}" .cc)

# Create a wrapper script to run the simulation
cat > "${NS3_DIR}/run-simulation.sh" << EOF
#!/bin/bash

# Run the NS-3 simulation
${NS3_DIR}/waf --run "${SIMULATION_NAME} --duration=300 --interval=1.0"

# Check if the simulation ran successfully
if [ \$? -eq 0 ]; then
    echo -e "${GREEN}✓ Simulation completed successfully${NC}"
else
    echo -e "${RED}✗ Simulation failed${NC}"
    exit 1
fi
EOF

# Make the wrapper script executable
chmod +x "${NS3_DIR}/run-simulation.sh"

echo -e "${GREEN}✓ NS-3 simulation setup complete${NC}"
echo -e "\nTo run the simulation, execute:\n  ${NS3_DIR}/run-simulation.sh"
echo -e "\nTo run with custom parameters:\n  cd ${NS3_DIR} && ./waf --run \"${SIMULATION_NAME} --duration=600 --interval=2.0\""

exit 0
