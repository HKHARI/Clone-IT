#!/usr/bin/env bash
set -e

VENV_DIR=".venv"
REQUIREMENTS="requirements-ui.txt"
ENTRY_POINT="app.py"

# --- Locate Python 3 ---
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
        major=$(echo "$version" | cut -d. -f1)
        if [ "$major" = "3" ]; then
            PYTHON="$cmd"
            PY_VERSION="$version"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3 is required but not found."
    echo "       Install it from https://www.python.org/downloads/"
    exit 1
fi

echo "Using $($PYTHON --version) at $(command -v $PYTHON)"

# --- Create virtual environment if missing ---
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."

    if ! "$PYTHON" -m venv "$VENV_DIR" 2>/dev/null; then
        # venv creation failed — likely missing python3-venv on Debian/Ubuntu
        OS="$(uname -s)"

        if [ "$OS" = "Linux" ] && command -v apt-get &>/dev/null; then
            echo ""
            echo "python3-venv package is missing. Installing it now..."
            sudo apt-get update -qq && sudo apt-get install -y -qq "python${PY_VERSION}-venv"
            echo ""
            echo "Retrying virtual environment creation..."
            "$PYTHON" -m venv "$VENV_DIR"
        elif [ "$OS" = "Linux" ] && command -v dnf &>/dev/null; then
            echo ""
            echo "python3-venv is missing. Installing it now..."
            sudo dnf install -y "python${PY_VERSION/./}-devel" || sudo dnf install -y python3-devel
            echo ""
            echo "Retrying virtual environment creation..."
            "$PYTHON" -m venv "$VENV_DIR"
        else
            echo ""
            echo "ERROR: Failed to create virtual environment."
            echo "       Please install the python3-venv package for your system:"
            echo "         Debian/Ubuntu: sudo apt install python${PY_VERSION}-venv"
            echo "         Fedora/RHEL:   sudo dnf install python3-devel"
            echo "         macOS:         venv is included with Python 3 from python.org or Homebrew"
            exit 1
        fi
    fi
fi

# --- Activate virtual environment ---
source "$VENV_DIR/bin/activate"

# --- Install / update dependencies ---
pip install --quiet --upgrade pip
pip install --quiet -r "$REQUIREMENTS"

# --- Run the web UI ---
python "$ENTRY_POINT"
