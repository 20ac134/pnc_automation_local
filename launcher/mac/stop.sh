#!/bin/bash
#
# stop.sh - Stop PnC Automation Tool on macOS
#

BACKEND_PORT=8000
FRONTEND_PORT=5173

echo "========================================"
echo "Stopping PnC Automation Tool"
echo "========================================"
echo ""

stop_port() {
  local PORT=$1
  local LABEL=$2

  echo "Stopping $LABEL on port $PORT..."

  local PIDS
  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null || true)

  if [ -z "$PIDS" ]; then
    echo "  No process found on port $PORT."
    return
  fi

  kill $PIDS 2>/dev/null || true
  sleep 2

  PIDS=$(lsof -ti tcp:$PORT 2>/dev/null || true)

  if [ -n "$PIDS" ]; then
    echo "  Process did not stop cleanly. Force killing..."
    kill -9 $PIDS 2>/dev/null || true
  fi

  echo "  $LABEL stopped."
}

stop_port $BACKEND_PORT "backend"
echo ""
stop_port $FRONTEND_PORT "frontend"

echo ""
echo "========================================"
echo "PnC Automation Tool stopped."
echo "========================================"