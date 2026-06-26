#!/bin/bash
# Fail on any error
set -e

echo "Starting Uvicorn..."
uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} &
UVICORN_PID=$!

echo "Starting LiveKit Voice Agent Worker..."
python backend/voice_agent.py start &
WORKER_PID=$!

# Wait for any process to exit
wait -n

echo "One of the processes exited. Shutting down..."
kill $UVICORN_PID
kill $WORKER_PID
exit 1
