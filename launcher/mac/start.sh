#!/bin/bash
#
# start.sh - Start PnC Automation Tool on macOS
#

set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BACKEND_DIR="$ROOT/vosyn-automation"
FRONTEND_DIR="$ROOT/university-job-portal/university-job-portal"

BACKEND_PORT=8000
FRONTEND_PORT=5173

BACKEND_LOG="/tmp/pnc-backend.log"
FRONTEND_LOG="/tmp/pnc-frontend.log"

echo "========================================"
echo "Starting PnC Automation Tool"
echo "========================================"
echo ""
echo "Root folder:"
echo "$ROOT"
echo ""

if [ ! -d "$BACKEND_DIR" ]; then
  echo "ERROR: Backend folder not found:"
  echo "$BACKEND_DIR"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR" ]; then
  echo "ERROR: Frontend folder not found:"
  echo "$FRONTEND_DIR"
  exit 1
fi

if [ ! -x "$BACKEND_DIR/env/bin/python" ]; then
  echo "ERROR: Backend virtual environment not found or broken."
  echo "Run this first:"
  echo "  ./launcher/mac/setup.sh"
  exit 1
fi

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "ERROR: Frontend node_modules not found."
  echo "Run this first:"
  echo "  ./launcher/mac/setup.sh"
  exit 1
fi

if lsof -ti tcp:$BACKEND_PORT >/dev/null 2>&1; then
  echo "ERROR: Port $BACKEND_PORT is already in use."
  echo "Run:"
  echo "  ./launcher/mac/stop.sh"
  exit 1
fi

if lsof -ti tcp:$FRONTEND_PORT >/dev/null 2>&1; then
  echo "ERROR: Port $FRONTEND_PORT is already in use."
  echo "Run:"
  echo "  ./launcher/mac/stop.sh"
  exit 1
fi

echo "Starting backend..."
echo "Backend logs: $BACKEND_LOG"

cd "$BACKEND_DIR"

./env/bin/python -m uvicorn src.API.api:app --host 127.0.0.1 --port $BACKEND_PORT > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

echo "Waiting for backend to be ready..."

for i in {1..30}; do
  if curl -s "http://127.0.0.1:$BACKEND_PORT" >/dev/null 2>&1; then
    echo "Backend is up."
    break
  fi

  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "ERROR: Backend exited during startup."
    echo "Last backend log lines:"
    echo "----------------------------------------"
    tail -n 30 "$BACKEND_LOG"
    echo "----------------------------------------"
    exit 1
  fi

  sleep 1

  if [ "$i" -eq 30 ]; then
    echo "ERROR: Backend did not become ready within 30 seconds."
    echo "See backend log:"
    echo "$BACKEND_LOG"
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
  fi
done

echo "Starting frontend..."
echo "Frontend logs: $FRONTEND_LOG"

cd "$FRONTEND_DIR"

npm run dev -- --host 127.0.0.1 --port $FRONTEND_PORT > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

echo "Waiting for frontend to be ready..."

for i in {1..30}; do
  if curl -s "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1; then
    echo "Frontend is up."
    break
  fi

  if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
    echo "ERROR: Frontend exited during startup."
    echo "Last frontend log lines:"
    echo "----------------------------------------"
    tail -n 30 "$FRONTEND_LOG"
    echo "----------------------------------------"
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
  fi

  sleep 1

  if [ "$i" -eq 30 ]; then
    echo "ERROR: Frontend did not become ready within 30 seconds."
    echo "See frontend log:"
    echo "$FRONTEND_LOG"
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
    exit 1
  fi
done

echo "Opening app..."
open "http://127.0.0.1:$FRONTEND_PORT"

echo ""
echo "========================================"
echo "PnC Automation Tool started."
echo "Backend:  http://127.0.0.1:$BACKEND_PORT"
echo "Frontend: http://127.0.0.1:$FRONTEND_PORT"
echo ""
echo "Logs:"
echo "  tail -f $BACKEND_LOG"
echo "  tail -f $FRONTEND_LOG"
echo ""
echo "Keep this terminal open while using the tool."
echo "Press Ctrl+C to stop."
echo "========================================"
echo ""

cleanup() {
  echo ""
  echo "Stopping PnC Automation Tool..."

  PIDS=$(lsof -ti tcp:$BACKEND_PORT tcp:$FRONTEND_PORT 2>/dev/null || true)

  if [ -n "$PIDS" ]; then
    kill $PIDS 2>/dev/null || true
    sleep 2

    PIDS=$(lsof -ti tcp:$BACKEND_PORT tcp:$FRONTEND_PORT 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
      kill -9 $PIDS 2>/dev/null || true
    fi
  fi

  echo "Stopped."
  exit 0
}

trap cleanup INT TERM

wait