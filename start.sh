#!/bin/bash
# Backend startup script for burglary alert system

echo "🚀 Starting Burglary Alert Backend..."

# Check if running in virtual environment
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
fi

# Install/update dependencies
echo "📚 Checking dependencies..."
pip3 install -q -r requirements.txt 2>/dev/null || pip install -q -r requirements.txt

# Start backend
echo "▶️  Starting server on http://0.0.0.0:8000"
echo "📖 API docs: http://localhost:8000/docs"
echo "🔒 Burglary API: http://localhost:8000/api/v1/burglary/"
echo ""

python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
