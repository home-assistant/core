#!/bin/bash
# Quick local check script for ONVIF changes before pushing

set -e

echo "🔍 Running local checks for ONVIF integration..."
echo ""

# Activate venv
source ~/dev/ha-test-venv/bin/activate

# Run ruff check
echo "▶️  Running ruff check..."
ruff check homeassistant/components/onvif/ tests/components/onvif/ || exit 1

# Run ruff format check  
echo "▶️  Running ruff format check..."
ruff format --check homeassistant/components/onvif/ tests/components/onvif/ || exit 1

# Run mypy only on ONVIF files
echo "▶️  Running mypy on ONVIF files..."
if command -v mypy &> /dev/null; then
    mypy homeassistant/components/onvif/ --no-error-summary 2>&1 | grep -E "^homeassistant/components/onvif/" || echo "  No ONVIF-specific errors"
else
    echo "⚠️  mypy not installed, skipping"
fi

echo ""
echo "✅ All local checks passed!"
echo ""
echo "💡 Tips:"
echo "   - Full pytest requires Python 3.14.2+ (not yet available in pyenv)"
echo "   - Tests will run in CI automatically"
echo "   - To run full prek checks: prek run"
