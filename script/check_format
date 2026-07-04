#!/bin/sh
# Format code with ruff-format.

cd "$(dirname "$0")/.."

ruff \
  format \
  --check \
  --quiet \
  homeassistant tests script *.py
