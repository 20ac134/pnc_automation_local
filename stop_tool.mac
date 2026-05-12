#!/bin/bash

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BACKEND_PORT=8000
FRONTEND_PORT=5173

echo "========================================"
echo "Stopping PnC Automation Tool"
echo "========================================"
echo

# Helper: try SIGTERM first so processes can clean up,
# then SIGKILL anything that didn't exit. Avoids leaving the
# port in TIME_WAIT, which would block an immediate restart.
stop_port() {
  local PORT=$1
  local LABEL=$2

  echo "Stopping $LABEL on port $PORT..."
  local PIDS
  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null)

  if [ -z "$PIDS" ]; then
    echo "  No process found on port $PORT."
    return
  fi

  # Graceful shutdown
  kill $PIDS 2>/dev/null
  sleep 2

  # Anything still alive gets force-killed
  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null)
  if [ -n "$PIDS" ]; then
    echo "  Process did not exit cleanly. Forcing..."
    kill -9 $PIDS 2>/dev/null
  fi

  echo "  $LABEL stopped."
}

stop_port $BACKEND_PORT "backend"
echo
stop_port $FRONTEND_PORT "frontend"

echo
echo "========================================"
echo "PnC Automation Tool stopped."
echo "========================================"