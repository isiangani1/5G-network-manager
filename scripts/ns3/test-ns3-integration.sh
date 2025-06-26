#!/bin/bash

# Test script for NS-3 integration with 5G Slicing Manager

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DURATION=300  # 5 minutes
INTERVAL=1.0  # 1 second
SLICE_ID="test-slice-$(date +%s)"
API_URL="http://localhost:8000/api"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--duration)
            DURATION="$2"
            shift 2
            ;;
        -i|--interval)
            INTERVAL="$2"
            shift 2
            ;;
        -s|--slice-id)
            SLICE_ID="$2"
            shift 2
            ;;
        -u|--url)
            API_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}=== 5G Slicing NS-3 Integration Test ===${NC}"
echo -e "Duration:  ${DURATION} seconds"
echo -e "Interval:  ${INTERVAL} seconds"
echo -e "Slice ID:  ${SLICE_ID}"
echo -e "API URL:   ${API_URL}"
echo ""

# Check if required commands are installed
for cmd in curl jq python3; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is required but not installed.${NC}"
        exit 1
    fi
done

# Function to print a progress bar
progress_bar() {
    local duration=$1
    local interval=$2
    local elapsed=0
    local total_ticks=50
    
    echo -e "\n${BLUE}Running test for ${duration} seconds...${NC}"
    
    while [ $elapsed -le $duration ]; do
        local progress=$((elapsed * total_ticks / duration))
        local remaining=$((total_ticks - progress))
        
        printf "\r${GREEN}["
        printf "%${progress}s" | tr ' ' '#'
        printf "%${remaining}s" | tr ' ' ' '
        printf "] ${elapsed}/${duration}s"
        
        sleep $interval
        elapsed=$((elapsed + 1))
    done
    printf "\n\n"
}

# Function to send test data
send_test_data() {
    local slice_id=$1
    local timestamp=$(date +%s)
    
    # Generate random metrics
    local latency=$(awk -v min=1 -v max=100 'BEGIN{srand(); print min+rand()*(max-min+1)}')
    local jitter=$(awk -v min=0.1 -v max=10 'BEGIN{srand(); print min+rand()*(max-min+1)}')
    local throughput=$(awk -v min=10 -v max=1000 'BEGIN{srand(); print int(min+rand()*(max-min+1))}')
    local packet_loss=$(awk -v min=0 -v max=0.1 'BEGIN{srand(); print min+rand()*(max-min+1)}')
    
    # Create JSON payload
    local payload=$(cat <<EOF
{
    "slice_id": "$slice_id",
    "timestamp": $timestamp,
    "metrics": {
        "latency_ms": $latency,
        "jitter_ms": $jitter,
        "throughput_mbps": $throughput,
        "packet_loss_rate": $packet_loss,
        "sla_breach": false
    }
}
EOF
)

    # Send data to API
    local response=$(curl -s -X POST "${API_URL}/ns3/kpi" \
        -H "Content-Type: application/json" \
        -d "$payload")
    
    if [ $? -ne 0 ] || [ -z "$response" ]; then
        echo -e "${RED}✗ Failed to send data to API${NC}"
        return 1
    fi
    
    # Check for error in response
    if echo "$response" | jq -e '.error' > /dev/null; then
        echo -e "${YELLOW}⚠ API Error: $(echo $response | jq -r '.error')${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ Sent metrics: latency=${latency}ms, jitter=${jitter}ms, throughput=${throughput}Mbps, packet_loss=${packet_loss}%${NC}"
}

# Test API connectivity
echo -e "${BLUE}Testing API connectivity...${NC}"
api_status=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/health")

if [ "$api_status" != "200" ]; then
    echo -e "${RED}✗ API is not reachable at ${API_URL} (Status: ${api_status})${NC}"
    echo -e "${YELLOW}Make sure the API server is running and accessible.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ API is reachable${NC}"
fi

# Create a test slice if it doesn't exist
echo -e "\n${BLUE}Checking test slice...${NC}"
slice_exists=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}/slices/${SLICE_ID}")

if [ "$slice_exists" != "200" ]; then
    echo -e "${YELLOW}Creating test slice: ${SLICE_ID}${NC}"
    
    slice_data=$(cat <<EOF
{
    "slice_id": "$SLICE_ID",
    "name": "NS-3 Test Slice",
    "description": "Automatically created for NS-3 integration testing",
    "network_parameters": {
        "latency_max_ms": 100,
        "jitter_max_ms": 10,
        "throughput_min_mbps": 10,
        "packet_loss_max": 0.1
    },
    "enabled": true
}
EOF
)
    
    create_response=$(curl -s -X POST "${API_URL}/slices" \
        -H "Content-Type: application/json" \
        -d "$slice_data")
    
    if [ $? -ne 0 ] || [ -z "$create_response" ]; then
        echo -e "${RED}✗ Failed to create test slice${NC}"
        exit 1
    fi
    
    if echo "$create_response" | jq -e '.error' > /dev/null; then
        echo -e "${YELLOW}⚠ Failed to create slice: $(echo $create_response | jq -r '.error')${NC}"
    else
        echo -e "${GREEN}✓ Created test slice: ${SLICE_ID}${NC}"
    fi
else
    echo -e "${GREEN}✓ Using existing test slice: ${SLICE_ID}${NC}"
fi

# Start sending test data
echo -e "\n${BLUE}Starting to send test data...${NC}"
start_time=$(date +%s)
end_time=$((start_time + DURATION))
counter=0

while [ $(date +%s) -lt $end_time ]; do
    counter=$((counter + 1))
    echo -e "\n${BLUE}--- Test ${counter} ---${NC}"
    
    # Send test data
    if ! send_test_data "$SLICE_ID"; then
        echo -e "${YELLOW}Retrying in 1 second...${NC}"
        sleep 1
        continue
    fi
    
    # Get current slice status
    echo -e "\n${BLUE}Fetching slice status...${NC}"
    slice_status=$(curl -s "${API_URL}/slices/${SLICE_ID}")
    
    if [ $? -eq 0 ] && [ -n "$slice_status" ]; then
        echo "Current Metrics:"
        echo "  Latency:    $(echo $slice_status | jq -r '.current_metrics.latency_ms // "N/A"') ms"
        echo "  Jitter:     $(echo $slice_status | jq -r '.current_metrics.jitter_ms // "N/A"') ms"
        echo "  Throughput: $(echo $slice_status | jq -r '.current_metrics.throughput_mbps // "N/A"') Mbps"
        echo "  Packet Loss: $(echo $slice_status | jq -r 'if .current_metrics.packet_loss_rate then (.current_metrics.packet_loss_rate * 100) else "N/A" end')%"
        echo "  SLA Status: $(echo $slice_status | jq -r 'if .sla_violation then "${RED}VIOLATION${NC}" else "${GREEN}OK${NC}"')"
    else
        echo -e "${YELLOW}⚠ Failed to fetch slice status${NC}"
    fi
    
    # Calculate time remaining
    current_time=$(date +%s)
    time_remaining=$((end_time - current_time))
    
    if [ $time_remaining -gt 0 ]; then
        echo -e "\n${BLUE}Waiting ${INTERVAL}s before next update (${time_remaining}s remaining)...${NC}"
        sleep $INTERVAL
    fi
done

# Test completed
echo -e "\n${GREEN} Test completed successfully!${NC}"
echo -e "Test duration: ${DURATION} seconds"
echo -e "Total updates sent: ${counter}"
echo -e "\nYou can view the test results in the dashboard: http://localhost:8050"
echo -e "Or check the metrics in Grafana: http://localhost:3000"

# Keep the container running if in Docker
if [ "$KEEP_ALIVE" = "true" ]; then
    echo -e "\n${YELLOW}Container will stay alive as KEEP_ALIVE is set to true${NC}"
    tail -f /dev/null
fi

exit 0
