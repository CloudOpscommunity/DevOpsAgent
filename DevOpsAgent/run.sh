#!/bin/bash

echo "🚀 Starting OpsBot DevOps Agent..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} ✅ $1"
}

print_warning() {
    echo -e "${YELLOW}[$(date '+%H:%M:%S')]${NC} ⚠️  $1"
}

print_error() {
    echo -e "${RED}[$(date '+%H:%M:%S')]${NC} ❌ $1"
}

# Check if we're in the right directory
if [ ! -f "src/opsbot.py" ] && [ ! -f "opsbot.py" ]; then
    print_error "opsbot.py not found! Please run from project root or src directory."
    exit 1
fi

# Source environment variables if .env exists
if [ -f ".env" ]; then
    print_status "Loading environment variables from .env..."
    source .env
    print_success "Environment loaded"
else
    print_warning ".env file not found - using defaults"
fi

# Create necessary directories
print_status "Creating required directories..."
mkdir -p data logs
print_success "Directories created"

# Stop any existing processes
print_status "Stopping existing processes..."

# Stop existing Streamlit processes
STREAMLIT_PID=$(sudo lsof -i :8501 -t 2>/dev/null)
if [ -n "$STREAMLIT_PID" ]; then
    sudo kill -9 $STREAMLIT_PID
    print_success "Stopped existing Streamlit process (PID: $STREAMLIT_PID)"
    echo "Stopped existing Streamlit process (PID: $STREAMLIT_PID)" >> run.log
fi

# Stop existing OpsBot processes
OPSBOT_PID=$(ps aux | grep '[o]psbot.py' | awk '{print $2}')
if [ -n "$OPSBOT_PID" ]; then
    sudo kill -9 $OPSBOT_PID
    print_success "Stopped existing OpsBot process (PID: $OPSBOT_PID)"
    echo "Stopped existing OpsBot process (PID: $OPSBOT_PID)" >> run.log
fi

# Wait a moment for processes to fully stop
sleep 2

# Start Docker services if not running
print_status "Checking Docker services..."
if command -v docker-compose &> /dev/null; then
    if ! docker-compose ps | grep -q "Up"; then
        print_status "Starting Docker services (Prometheus, Node Exporter)..."
        docker-compose up -d
        print_success "Docker services started"
        sleep 5
    else
        print_success "Docker services already running"
    fi
else
    print_warning "docker-compose not found - skipping Docker services"
fi

# Ensure test container exists
print_status "Checking test container..."
CONTAINER_NAME="${CONTAINER_NAME:-test-container}"
if ! docker ps -a --format "{{.Names}}" | grep -q "^${CONTAINER_NAME}$"; then
    print_status "Creating test container: $CONTAINER_NAME"
    docker run -d --name "$CONTAINER_NAME" alpine:latest sh -c "while true; do sleep 1; done"
    print_success "Test container created"
else
    print_success "Test container exists"
fi

# Change to src directory if not already there
if [ -f "opsbot.py" ]; then
    SRC_DIR="."
else
    SRC_DIR="src"
    cd src
fi

# Start Streamlit UI in background
print_status "Starting Streamlit dashboard..."
nohup streamlit run ui.py --server.address 0.0.0.0 --server.port 8501 > ../streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "Started Streamlit UI (PID: $STREAMLIT_PID)" >> ../run.log
print_success "Streamlit started (PID: $STREAMLIT_PID) - Access at http://localhost:8501"

# Wait a moment for Streamlit to start
sleep 3

# Start OpsBot agent in background
print_status "Starting OpsBot monitoring agent..."
nohup python3 opsbot.py > ../opsbot.log 2>&1 &
OPSBOT_PID=$!
echo "Started OpsBot agent (PID: $OPSBOT_PID)" >> ../run.log
print_success "OpsBot started (PID: $OPSBOT_PID)"

# Wait a moment and check if processes are still running
sleep 2

# Verify processes are running
if ps -p $STREAMLIT_PID > /dev/null; then
    print_success "Streamlit UI is running"
else
    print_error "Streamlit failed to start"
fi

if ps -p $OPSBOT_PID > /dev/null; then
    print_success "OpsBot agent is running"
else
    print_error "OpsBot failed to start"
fi

# Display status and instructions
echo ""
echo "======================================"
echo "🤖 OpsBot DevOps Agent Status"
echo "======================================"
echo "📊 Dashboard URL: http://localhost:8501"
echo "📊 Prometheus URL: http://localhost:9090"
echo "🐳 Container: $CONTAINER_NAME"
echo ""
echo "📋 Process Information:"
echo "   Streamlit UI: PID $STREAMLIT_PID"
echo "   OpsBot Agent: PID $OPSBOT_PID"
echo ""
echo "📁 Log Files:"
echo "   OpsBot: ../opsbot.log"
echo "   Streamlit: ../streamlit.log"
echo "   Run history: ../run.log"
echo ""
echo "🔧 Control Commands:"
echo "   Stop all: pkill -f 'streamlit\|opsbot.py'"
echo "   View logs: tail -f ../opsbot.log"
echo "   Monitor: watch 'ps aux | grep -E \"streamlit|opsbot\"'"
echo ""
echo "✅ Both services are running in the background!"
echo "   The OpsBot will continuously monitor CPU usage"
echo "   Check the dashboard for real-time status"
echo ""

# Offer to tail logs
read -p "🔍 Would you like to monitor OpsBot logs? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Monitoring OpsBot logs (Ctrl+C to exit)..."
    tail -f ../opsbot.log
fi
