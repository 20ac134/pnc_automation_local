#!/bin/bash
#
# setup_mac.sh - PnC Automation Tool, macOS setup
#

set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# Minimum versions required
MIN_PY_MAJOR=3
MIN_PY_MINOR=10
MIN_NODE_MAJOR=18

# Versions to install via Homebrew when missing
PY_BREW_FORMULA="python@3.12"
NODE_BREW_FORMULA="node@20"

echo "========================================"
echo "PnC Automation Tool - Mac Setup"
echo "========================================"
echo ""
echo "Root folder:"
echo "$ROOT"
echo ""

# -------------------------------
# Check project folders
# -------------------------------
echo "Checking project folders..."

if [ ! -d "$ROOT/vosyn-automation" ]; then
  echo "ERROR: Backend folder not found:"
  echo "$ROOT/vosyn-automation"
  echo ""
  echo "Make sure this file is inside launcher/mac/"
  exit 1
fi

if [ ! -d "$ROOT/university-job-portal/university-job-portal" ]; then
  echo "ERROR: Frontend folder not found:"
  echo "$ROOT/university-job-portal/university-job-portal"
  exit 1
fi

echo "Project folders found."
echo ""

# -------------------------------
# Check Chrome (required for portal automation)
# -------------------------------
echo "Checking Chrome..."

if [ ! -d "/Applications/Google Chrome.app" ]; then
  echo "ERROR: Google Chrome not found in /Applications."
  echo "Please install Chrome from https://www.google.com/chrome/ and try again."
  exit 1
fi

echo "Google Chrome found."
echo ""

# -------------------------------
# Check / install Homebrew
# -------------------------------
echo "Checking Homebrew..."

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew not found. Installing..."
  echo "You will be asked for your Mac password (this is for Homebrew installation)."
  echo ""
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Load brew into PATH. Different paths on Apple Silicon vs Intel.
if [ -x "/opt/homebrew/bin/brew" ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x "/usr/local/bin/brew" ]; then
  eval "$(/usr/local/bin/brew shellenv)"
else
  echo "ERROR: Homebrew install reported success but brew is not on PATH."
  echo "Close Terminal, open a new one, and run setup_mac.sh again."
  exit 1
fi

echo "Homebrew ready."
echo ""

# -------------------------------
# Check Python (verified by running it, not by parsing version strings)
# -------------------------------
echo "Checking Python..."

PYTHON_CMD=""

# Try the brew-pinned version first.
PY_PIN_PREFIX="$(brew --prefix "$PY_BREW_FORMULA" 2>/dev/null || true)"
if [ -n "$PY_PIN_PREFIX" ] && [ -x "$PY_PIN_PREFIX/bin/python3.12" ]; then
  if "$PY_PIN_PREFIX/bin/python3.12" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_PY_MAJOR, $MIN_PY_MINOR) else 1)" >/dev/null 2>&1; then
    PYTHON_CMD="$PY_PIN_PREFIX/bin/python3.12"
  fi
fi

# Fall back to any python3 on PATH that meets the minimum.
if [ -z "$PYTHON_CMD" ]; then
  if command -v python3 >/dev/null 2>&1; then
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_PY_MAJOR, $MIN_PY_MINOR) else 1)" >/dev/null 2>&1; then
      PYTHON_CMD="$(command -v python3)"
    fi
  fi
fi

# Still nothing? Install via brew.
if [ -z "$PYTHON_CMD" ]; then
  echo "Python $MIN_PY_MAJOR.$MIN_PY_MINOR+ not found. Installing $PY_BREW_FORMULA..."
  brew install "$PY_BREW_FORMULA"

  PY_PIN_PREFIX="$(brew --prefix "$PY_BREW_FORMULA")"
  if [ -x "$PY_PIN_PREFIX/bin/python3.12" ]; then
    PYTHON_CMD="$PY_PIN_PREFIX/bin/python3.12"
  fi
fi

if [ -z "$PYTHON_CMD" ]; then
  echo "ERROR: Could not find or install a working Python."
  exit 1
fi

echo "Found Python: $PYTHON_CMD"
"$PYTHON_CMD" --version
echo "Python OK."
echo ""

# -------------------------------
# Check Node.js
# -------------------------------
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

  # node@20 is keg-only - link it so 'node' is on PATH.
  brew link --overwrite --force "$NODE_BREW_FORMULA" 2>/dev/null || true

  # Add node@20 bin to PATH for this session.
  NODE_PIN_PREFIX="$(brew --prefix "$NODE_BREW_FORMULA" 2>/dev/null || true)"
  if [ -n "$NODE_PIN_PREFIX" ] && [ -d "$NODE_PIN_PREFIX/bin" ]; then
    export PATH="$NODE_PIN_PREFIX/bin:$PATH"
  fi

  if ! command -v node >/dev/null 2>&1; then
    echo "ERROR: Node install reported success but 'node' is not on PATH."
    echo "Close Terminal, open a new one, and run setup_mac.sh again."
    exit 1
  fi
fi

echo "Found Node.js: $(command -v node)"
node --version
echo "Node.js OK."
echo ""

# -------------------------------
# Check npm (ships with Node, but verify)
# -------------------------------
echo "Checking npm..."

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Try: brew reinstall $NODE_BREW_FORMULA"
  exit 1
fi

echo "Found npm: $(command -v npm)"
npm --version
echo "npm OK."
echo ""

# -------------------------------
# Backend setup
# -------------------------------
echo "========================================"
echo "Setting up backend"
echo "========================================"
echo ""

cd "$ROOT/vosyn-automation"

if [ ! -f "requirements.txt" ]; then
  echo "ERROR: requirements.txt not found in $(pwd)"
  exit 1
fi

# Detect and rebuild broken venvs.
REBUILD_VENV=0
if [ -d "env" ]; then
  if [ ! -x "env/bin/python" ]; then
    REBUILD_VENV=1
  elif ! env/bin/python -c "import sys" >/dev/null 2>&1; then
    REBUILD_VENV=1
  fi
fi

if [ "$REBUILD_VENV" -eq 1 ]; then
  echo "Found broken virtual environment. Removing and recreating..."
  rm -rf env
fi

if [ ! -d "env" ]; then
  echo "Creating Python virtual environment..."
  "$PYTHON_CMD" -m venv env

  if [ ! -x "env/bin/python" ]; then
    echo "ERROR: venv reported success but env/bin/python is missing."
    exit 1
  fi
else
  echo "Backend virtual environment is healthy."
fi

VENV_PY="$ROOT/vosyn-automation/env/bin/python"

echo "Upgrading pip..."
"$VENV_PY" -m pip install --upgrade pip

echo "Installing backend dependencies..."
"$VENV_PY" -m pip install -r requirements.txt

echo ""

# -------------------------------
# Frontend setup
# -------------------------------
echo "========================================"
echo "Setting up frontend"
echo "========================================"
echo ""

cd "$ROOT/university-job-portal/university-job-portal"

if [ ! -f "package.json" ]; then
  echo "ERROR: package.json not found in $(pwd)"
  exit 1
fi

if [ ! -d "node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install
else
  echo "Frontend dependencies already installed."
fi

echo ""
echo "========================================"
echo "Setup complete."
echo "Now run:"
echo "  ./launcher/mac/start_pnc_tool_mac.sh"
echo "========================================"
