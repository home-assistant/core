#!/bin/sh
# Launch the application and any extra required processes locally.

# Stop on errors
set -e

cd "$(dirname "$0")/.."

# Ensure translations are up to date
python3 -m script.translations develop --all

# Start Home Assistant
python3 -m homeassistant -c config
