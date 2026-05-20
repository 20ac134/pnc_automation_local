#!/bin/bash
#
# setup.sh - PnC Automation Tool macOS setup
#

set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

BACKEND_DIR="$ROOT/vosyn-automation"
FRONTEND_DIR="$ROOT/university-job-portal/university-job-portal"

MIN_PY_MAJOR=3
MIN_PY_MINOR=10
MIN_NODE_MAJOR=18

PY_BREW_FORMULA="python@3.12"
NODE_BREW_FORMULA="node@20"

echo "========================================"
echo "PnC Automation Tool - Mac Setup"
echo "========================================"
echo ""
echo "Root folder:"
echo "$ROOT"
echo ""

echo "Checking project folders..."

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

echo "Project folders found."
echo ""

echo "Checking Google Chrome..."

if [ ! -d "/Applications/Google Chrome.app" ]; then
  echo "ERROR: Google Chrome is required for portal automation."
  echo "Install Chrome, then run setup again:"
  echo "https://www.google.com/chrome/"
  exit 1
fi

echo "Google Chrome found."
echo ""

echo "Checking Homebrew..."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Installing Homebrew..."
  echo "You may be asked for your Mac password."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if [ -x "/opt/homebrew/bin/brew" ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x "/usr/local/bin/brew" ]; then
  eval "$(/usr/local/bin/brew shellenv)"
else
  echo "ERROR: Homebrew was installed but could not be found on PATH."
  echo "Close Terminal, reopen it, and run setup again."
  exit 1
fi

echo "Homebrew ready."
echo ""

echo "Checking Python..."

PYTHON_CMD=""

PY_PIN_PREFIX="$(brew --prefix "$PY_BREW_FORMULA" 2>/dev/null || true)"

if [ -n "$PY_PIN_PREFIX" ] && [ -x "$PY_PIN_PREFIX/bin/python3.12" ]; then
  if "$PY_PIN_PREFIX/bin/python3.12" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_PY_MAJOR, $MIN_PY_MINOR) else 1)" >/dev/null 2>&1; then
    PYTHON_CMD="$PY_PIN_PREFIX/bin/python3.12"
  fi
fi

if [ -z "$PYTHON_CMD" ] && command -v python3 >/dev/null 2>&1; then
  if python3 -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_PY_MAJOR, $MIN_PY_MINOR) else 1)" >/dev/null 2>&1; then
    PYTHON_CMD="$(command -v python3)"
  fi
fi

if [ -z "$PYTHON_CMD" ]; then
  echo "Python $MIN_PY_MAJOR.$MIN_PY_MINOR+ not found. Installing $PY_BREW_FORMULA..."
  brew install "$PY_BREW_FORMULA"

  PY_PIN_PREFIX="$(brew --prefix "$PY_BREW_FORMULA")"
  if [ -x "$PY_PIN_PREFIX/bin/python3.12" ]; then
    PYTHON_CMD="$PY_PIN_PREFIX/bin/python3.12"
  fi
fi

if [ -z "$PYTHON_CMD" ]; then
  echo "ERROR: Could not find or install Python."
  exit 1
fi

echo "Found Python: $PYTHON_CMD"
"$PYTHON_CMD" --version
echo ""

echo "Checking Node.js..."

NODE_OK=0

if command -v node >/dev/null 2>&1; then
  if node -e "process.exit(parseInt(process.versions.node.split('.')[0]) >= $MIN_NODE_MAJOR ? 0 : 1)" >/dev/null 2>&1; then
    NODE_OK=1
  fi
fi

if [ "$NODE_OK" -eq 0 ]; then
  echo "Node.js $MIN_NODE_MAJOR+ not found. Installing $NODE_BREW_FORMULA..."
  brew install "$NODE_BREW_FORMULA"

  brew link --overwrite --force "$NODE_BREW_FORMULA" 2>/dev/null || true

  NODE_PIN_PREFIX="$(brew --prefix "$NODE_BREW_FORMULA" 2>/dev/null || true)"
  if [ -n "$NODE_PIN_PREFIX" ] && [ -d "$NODE_PIN_PREFIX/bin" ]; then
    export PATH="$NODE_PIN_PREFIX/bin:$PATH"
  fi
fi

if ! command -v node >/dev/null 2>&1; then
  echo "ERROR: Node.js install completed but node is not on PATH."
  echo "Close Terminal, reopen it, and run setup again."
  exit 1
fi

echo "Found Node.js: $(command -v node)"
node --version
echo ""

echo "Checking npm..."

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found."
  echo "Try running: brew reinstall $NODE_BREW_FORMULA"
  exit 1
fi

echo "Found npm: $(command -v npm)"
npm --version
echo ""

echo "========================================"
echo "Setting up backend"
echo "========================================"
echo ""

cd "$BACKEND_DIR"

if [ ! -f "requirements.txt" ]; then
  echo "ERROR: requirements.txt not found in:"
  echo "$BACKEND_DIR"
  exit 1
fi

REBUILD_VENV=0

if [ -d "env" ]; then
  if [ ! -x "env/bin/python" ]; then
    REBUILD_VENV=1
  elif ! env/bin/python -c "import sys" >/dev/null 2>&1; then
    REBUILD_VENV=1
  fi
fi

if [ "$REBUILD_VENV" -eq 1 ]; then
  echo "Broken backend virtual environment found. Recreating..."
  rm -rf env
fi

if [ ! -d "env" ]; then
  echo "Creating backend virtual environment..."
  "$PYTHON_CMD" -m venv env
else
  echo "Backend virtual environment already exists."
fi

VENV_PY="$BACKEND_DIR/env/bin/python"

echo "Upgrading pip..."
"$VENV_PY" -m pip install --upgrade pip

echo "Installing backend dependencies..."
"$VENV_PY" -m pip install -r requirements.txt

echo ""

echo "========================================"
echo "Setting up frontend"
echo "========================================"
echo ""

cd "$FRONTEND_DIR"

if [ ! -f "package.json" ]; then
  echo "ERROR: package.json not found in:"
  echo "$FRONTEND_DIR"
  exit 1
fi

if [ -f "package-lock.json" ]; then
  echo "Installing frontend dependencies using npm ci..."
  npm ci
else
  echo "Installing frontend dependencies using npm install..."
  npm install
fi

echo ""
echo "========================================"
echo "Setup complete."
echo "Now run:"
echo "  ./launcher/mac/start.sh"
echo "========================================"