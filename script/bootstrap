#!/bin/sh
# Resolve all dependencies that the application requires to run.

# Stop on errors
set -e

cd "$(dirname "$0")/.."

echo "Installing development dependencies..."
uv pip install wheel --constraint homeassistant/package_constraints.txt --upgrade
uv pip install colorlog $(grep awesomeversion requirements.txt) --constraint homeassistant/package_constraints.txt --upgrade
uv pip install -r requirements_test.txt -c homeassistant/package_constraints.txt --upgrade
