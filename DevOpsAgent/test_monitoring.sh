#!/bin/bash

echo "🧪 Testing OpsBot Monitoring System"
echo "=================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# Test 1: Check if OpsBot is running
print_step "Checking if OpsBot is running..."
if ps aux | grep -q '[o]psbot.py'; then
    print_success "OpsBot process found"
else
    print_info "OpsBot not running - start it with ./run.sh"
    exit 1
fi

# Test 2: Check if Streamlit is running
print_step "Checking if Streamlit dashboard is running..."
if ps aux | grep -q '[s]treamlit'; then
    print_success "Streamlit dashboard found"
    print_info "Dashboard available at: http://localhost:8501"
else
    print_info "Streamlit not running"
fi

# Test 3: Check data files
print_step "Checking data files..."
if [ -f "data/ui_data.json" ]; then
    print_success "UI data file exists"
    echo "Current CPU usage: $(cat data/ui_data.json | grep -o '"cpu_usage": [0-9.]*' | cut -d: -f2 | tr -d ' ')"
else
    print_info "UI data file not found"
fi

if [ -f "data/incidents.db" ]; then
    print_success "Incidents database exists"
    INCIDENT_COUNT=$(sqlite3 data/incidents.db "SELECT COUNT(*) FROM incidents;" 2>/dev/null || echo "0")
    echo "Total incidents logged: $INCIDENT_COUNT"
else
    print_info "Incidents database not found"
fi

# Test 4: Check Docker containers
print_step "Checking Docker containers..."
CONTAINER_NAME="${CONTAINER_NAME:-test-container}"
if docker ps | grep -q "$CONTAINER_NAME"; then
    print_success "Test container '$CONTAINER_NAME' is running"
else
    print_info "Test container not found - creating it..."
    docker run -d --name "$CONTAINER_NAME" alpine:latest sh -c "while true; do sleep 1; done"
    print_success "Test container created"
fi

# Test 5: Simulate CPU spike for testing
print_step "Would you like to simulate a CPU spike for testing? (y/N)"
read -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Simulating CPU spike by updating UI data..."

    cat > data/ui_data.json << EOF
{
  "cpu_usage": 95.0,
  "status": "Spike Detected",
  "last_updated": "$(date)",
  "container_name": "$CONTAINER_NAME",
  "threshold": 80,
  "monitoring_active": true
}
EOF

    print_success "CPU spike simulated! Check the dashboard to see the change"
    print_info "OpsBot should detect this spike in the next monitoring cycle"
fi

# Test 6: Show recent logs
print_step "Showing recent OpsBot logs..."
if [ -f "opsbot.log" ]; then
    echo "Last 10 lines from opsbot.log:"
    tail -10 opsbot.log
elif [ -f "../opsbot.log" ]; then
    echo "Last 10 lines from ../opsbot.log:"
    tail -10 ../opsbot.log
else
    print_info "No log file found"
fi

echo ""
echo "🎯 Test Summary:"
echo "- Check dashboard: http://localhost:8501"
echo "- Monitor logs: tail -f opsbot.log (or ../opsbot.log)"
echo "- View processes: ps aux | grep -E 'opsbot|streamlit'"
echo "- Stop services: pkill -f 'opsbot\\.py|streamlit'"
echo ""
echo "✅ Testing complete!"
