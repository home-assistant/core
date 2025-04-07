#!/bin/sh
# Run monkeytype on test suite or optionally on a test module or directory.

# Stop on errors
set -e

cd "$(dirname "$0")/.."

command -v pytest >/dev/null 2>&1 || {
  echo >&2 "This script requires pytest but it's not installed." \
    "Aborting. Try: uv pip install pytest"; exit 1; }

command -v monkeytype >/dev/null 2>&1 || {
  echo >&2 "This script requires monkeytype but it's not installed." \
    "Aborting. Try: uv pip install monkeytype"; exit 1; }

if [ $# -eq 0 ]
  then
    echo "Run monkeytype on test suite"
    monkeytype run "`command -v pytest`"
    exit
fi

echo "Run monkeytype on tests in $1"
monkeytype run "`command -v pytest`" "$1"
