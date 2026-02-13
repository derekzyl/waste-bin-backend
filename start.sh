#!/bin/bash
# Backend startup script for burglary alert system

echo "🚀 Starting Burglary Alert Backend with uv..."

# Sync dependencies
echo "📚 Syncing dependencies..."
uv sync

# Start backend
echo "▶️  Starting server on http://0.0.0.0:8000"
echo "📖 API docs: http://localhost:8000/docs"
echo "🔒 Burglary API: http://localhost:8000/api/v1/burglary/"
echo ""

# Force venv usage to avoid system package interference (fixes numpy issue)
export PYTHONPATH=.venv/lib/python3.13/site-packages

uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
