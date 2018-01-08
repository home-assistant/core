#!/bin/sh
# Update application to run for its current checkout.

# Stop on errors
set -e

cd "$(dirname "$0")/.."
git pull
git submodule update
