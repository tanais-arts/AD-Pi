#!/bin/bash
# run_server.sh — Launch the Rythmo Sync web server on Raspberry Pi 400
# 
# Usage:
#   ./run_server.sh              # Start on default port 8080
#   ./run_server.sh --port 9000  # Start on custom port 9000
#   ./run_server.sh --help       # Show help

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default port
PORT=8080

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --help|-h)
            echo "Rythmo Sync Server — Raspberry Pi 400"
            echo ""
            echo "Usage: ./run_server.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT    Server port (default: 8080)"
            echo "  --help         Show this help message"
            echo ""
            echo "Examples:"
            echo "  ./run_server.sh              # Start on http://0.0.0.0:8080"
            echo "  ./run_server.sh --port 9000 # Start on http://0.0.0.0:9000"
            echo ""
            echo "Access from your computer:"
            echo "  http://<pi-ip-address>:8080"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if venv exists
if [ ! -d "venv" ]; then
    echo "❌ Error: Python virtual environment not found at ./venv"
    echo ""
    echo "Please run the installer first:"
    echo "  chmod +x install.sh"
    echo "  ./install.sh"
    exit 1
fi

# Activate venv
source venv/bin/activate

# Get the Pi's IP address
PI_IP=$(hostname -I | awk '{print $1}')

# Display startup message
echo "════════════════════════════════════════════════════════════════"
echo "🎬 Rythmo Sync Server — Raspberry Pi 400"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "✅ Server starting on port $PORT"
echo ""
echo "🌐 Access from your computer or phone:"
echo "   http://$PI_IP:$PORT"
echo ""
echo "📂 Working directory: $SCRIPT_DIR"
echo ""
echo "Press Ctrl+C to stop the server"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Start the server
python3 server.py --port "$PORT" --host 0.0.0.0
