#!/bin/sh
# Replace the shell so termination signals reach the worker.
set -eu

: "${SANDBOX_NAME:?SANDBOX_NAME is required (the sandbox group, e.g. built-in / custom)}"

exec python -m hass_client.sandbox \
  --name "${SANDBOX_NAME}" \
  --url "${SANDBOX_URL:-stdio://}" \
  --log-level "${SANDBOX_LOG_LEVEL:-INFO}"
