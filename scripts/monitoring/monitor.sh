#!/bin/bash

# Database and Application Monitoring Script
# This script monitors the health and performance of the 5G Slicing Manager

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Load environment variables
if [ -f "../../.env" ]; then
    export $(grep -v '^#' ../../.env | xargs)
else
    echo -e "${YELLOW}Warning: .env file not found. Using default values.${NC}"
fi

# Default values
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-slicing_manager}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-postgres}
API_URL=${API_URL:-http://localhost:8000}
LOG_FILE="../../logs/monitoring.log"
CHECK_INTERVAL=300  # 5 minutes in seconds

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages with timestamp
log() {
    local level=$1
    local message=$2
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local log_entry="[$timestamp] [$level] $message"
    
    # Log to console with colors
    case $level in
        "INFO") echo -e "${BLUE}[INFO]${NC} $message" ;;
        "WARN") echo -e "${YELLOW}[WARN]${NC} $message" ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} $message" ;;
        "SUCCESS") echo -e "${GREEN}[SUCCESS]${NC} $message" ;;
        *) echo "[$level] $message" ;;
    esac
    
    # Log to file
    echo "$log_entry" >> "$LOG_FILE"
}

# Function to check database connection
check_database_connection() {
    log "INFO" "Checking database connection to ${DB_HOST}:${DB_PORT}/${DB_NAME}..."
    
    local start_time=$(date +%s%N)
    
    if PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1" &>/dev/null; then
        local end_time=$(date +%s%N)
        local duration=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
        
        log "SUCCESS" "Database connection successful (${duration}ms)"
        return 0
    else
        log "ERROR" "Failed to connect to database"
        return 1
    fi
}

# Function to check database health
check_database_health() {
    log "INFO" "Checking database health..."
    
    # Check if database is accepting connections
    if ! check_database_connection; then
        return 1
    fi
    
    # Get database size
    local db_size=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT pg_size_pretty(pg_database_size('${DB_NAME}'))" | xargs)
    
    # Get number of active connections
    local active_connections=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT count(*) FROM pg_stat_activity WHERE datname = '${DB_NAME}'" | xargs)
    
    # Get number of locks
    local locks_count=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT count(*) FROM pg_locks" | xargs)
    
    # Get longest running query (in seconds)
    local longest_query=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT COALESCE(EXTRACT(EPOCH FROM (NOW() - query_start)), 0)::int 
        FROM pg_stat_activity 
        WHERE state = 'active' 
        AND query NOT LIKE '%pg_stat_activity%' 
        ORDER BY 1 DESC LIMIT 1" | xargs)
    
    # Get table sizes
    local table_sizes=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT 
            table_schema || '.' || table_name AS table,
            pg_size_pretty(pg_total_relation_size(table_schema || '.' || table_name)) AS size,
            pg_total_relation_size(table_schema || '.' || table_name) AS size_bytes
        FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY size_bytes DESC
        LIMIT 5" 2>/dev/null)
    
    log "INFO" "Database size: $db_size"
    log "INFO" "Active connections: $active_connections"
    log "INFO" "Active locks: $locks_count"
    
    if [ -n "$longest_query" ] && [ "$longest_query" != "0" ]; then
        log "WARN" "Longest running query: ${longest_query}s"
    fi
    
    if [ -n "$table_sizes" ]; then
        log "INFO" "Largest tables by size:"
        echo "$table_sizes" | while read -r line; do
            if [ -n "$line" ]; then
                log "INFO" "  $line"
            fi
        done
    fi
    
    return 0
}

# Function to check API health
check_api_health() {
    log "INFO" "Checking API health at ${API_URL}..."
    
    local start_time=$(date +%s%N)
    local response
    
    # Try to get the health endpoint
    response=$(curl -s -o /dev/null -w "%{http_code}" -m 5 "${API_URL}/health" 2>/dev/null)
    local curl_status=$?
    
    local end_time=$(date +%s%N)
    local duration=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
    
    if [ $curl_status -eq 0 ] && [ "$response" = "200" ]; then
        log "SUCCESS" "API is healthy (${duration}ms)"
        return 0
    else
        if [ $curl_status -ne 0 ]; then
            log "ERROR" "API request failed (cURL error: $curl_status)"
        else
            log "ERROR" "API returned non-200 status code: $response"
        fi
        return 1
    fi
}

# Function to check disk space
check_disk_space() {
    log "INFO" "Checking disk space..."
    
    # Get disk usage for the current partition
    local disk_usage=$(df -h . | awk 'NR==2 {print $5, $3, $2, $4}')
    local usage_percent=$(echo "$disk_usage" | awk '{print $1}' | tr -d '%')
    local used=$(echo "$disk_usage" | awk '{print $2}')
    local total=$(echo "$disk_usage" | awk '{print $3}')
    local avail=$(echo "$disk_usage" | awk '{print $4}')
    
    if [ "$usage_percent" -gt 90 ]; then
        log "ERROR" "Disk space critically low: ${usage_percent}% used (${used}/${total} used, ${avail} available)"
        return 1
    elif [ "$usage_percent" -gt 75 ]; then
        log "WARN" "Disk space getting low: ${usage_percent}% used (${used}/${total} used, ${avail} available)"
        return 0
    else
        log "SUCCESS" "Disk space OK: ${usage_percent}% used (${used}/${total} used, ${avail} available)"
        return 0
    fi
}

# Function to check system resources
check_system_resources() {
    log "INFO" "Checking system resources..."
    
    # Get CPU usage (average over 5 seconds)
    local cpu_usage=$(top -bn 2 -d 1 | grep '^%Cpu' | tail -n 1 | awk '{print 100 - $8}' | cut -d. -f1)
    
    # Get memory usage
    local mem_info=$(free -m | grep Mem)
    local mem_total=$(echo "$mem_info" | awk '{print $2}')
    local mem_used=$(echo "$mem_info" | awk '{print $3}')
    local mem_usage=$((mem_used * 100 / mem_total))
    
    # Get load average
    local load_avg=$(cat /proc/loadavg | awk '{print $1, $2, $3}')
    local cpu_cores=$(nproc)
    
    log "INFO" "CPU usage: ${cpu_usage}%"
    log "INFO" "Memory usage: ${mem_usage}% (${mem_used}M/${mem_total}M)"
    log "INFO" "Load average (1m, 5m, 15m): ${load_avg} (${cpu_cores} cores)"
    
    if [ "$cpu_usage" -gt 90 ]; then
        log "WARN" "High CPU usage detected: ${cpu_usage}%"
    fi
    
    if [ "$mem_usage" -gt 90 ]; then
        log "WARN" "High memory usage detected: ${mem_usage}%"
    fi
    
    return 0
}

# Function to check application logs for errors
check_application_logs() {
    local log_file="../../logs/application.log"
    
    if [ ! -f "$log_file" ]; then
        log "WARN" "Application log file not found: $log_file"
        return 0
    fi
    
    # Check for errors in the last 5 minutes
    local error_count=$(grep -a "ERROR" "$log_file" | awk -v d1="$(date -d '5 minutes ago' '+%Y-%m-%d %H:%M:%S')" \
        -v d2="$(date '+%Y-%m-%d %H:%M:%S')" '$0 > d1 && $0 < d2' | wc -l)
    
    if [ "$error_count" -gt 0 ]; then
        log "WARN" "Found $error_count ERROR level messages in the application logs in the last 5 minutes"
        
        # Get the last few error messages
        local last_errors=$(grep -a "ERROR" "$log_file" | tail -n 3)
        while IFS= read -r error; do
            log "WARN" "  $error"
        done <<< "$last_errors"
    else
        log "SUCCESS" "No ERROR level messages in the application logs in the last 5 minutes"
    fi
    
    return 0
}

# Main monitoring function
run_monitoring() {
    log "INFO" "Starting monitoring checks at $(date)"
    
    # Run all checks
    check_database_connection
    check_database_health
    check_api_health
    check_disk_space
    check_system_resources
    check_application_logs
    
    log "INFO" "Monitoring checks completed at $(date)"
    log "INFO" "----------------------------------------"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --db-host)
            DB_HOST="$2"
            shift 2
            ;;
        --db-port)
            DB_PORT="$2"
            shift 2
            ;;
        --db-name)
            DB_NAME="$2"
            shift 2
            ;;
        --db-user)
            DB_USER="$2"
            shift 2
            ;;
        --db-password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        --api-url)
            API_URL="$2"
            shift 2
            ;;
        --log-file)
            LOG_FILE="$2"
            shift 2
            ;;
        --interval)
            CHECK_INTERVAL="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  --db-host HOST       Database host (default: localhost)"
            echo "  --db-port PORT       Database port (default: 5432)"
            echo "  --db-name NAME       Database name (default: slicing_manager)"
            echo "  --db-user USER       Database user (default: postgres)"
            echo "  --db-password PASS   Database password (default: postgres)"
            echo "  --api-url URL        API base URL (default: http://localhost:8000)"
            echo "  --log-file FILE      Log file path (default: ../../logs/monitoring.log)"
            echo "  --interval SECONDS   Check interval in seconds (default: 300)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create logs directory if it doesn't exist
mkdir -p "$(dirname "$LOG_FILE")"

# Run in a loop if CHECK_INTERVAL is greater than 0
if [ "$CHECK_INTERVAL" -gt 0 ]; then
    log "INFO" "Starting monitoring with ${CHECK_INTERVAL}s interval. Press Ctrl+C to stop."
    
    while true; do
        run_monitoring
        sleep "$CHECK_INTERVAL"
    done
else
    # Run once
    run_monitoring
fi
