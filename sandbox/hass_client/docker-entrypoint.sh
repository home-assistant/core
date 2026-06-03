#!/bin/sh
# Entrypoint for the Sandbox runtime image.
#
# Expands the SANDBOX_* env vars into the runtime CLI flags and `exec`s the
# module so the Python process replaces this shell (tini, as PID 1, then
# forwards signals to it for a clean shutdown). The module name stays
# `hass_client.sandbox` — do not rename it here.
set -eu

: "${SANDBOX_NAME:?SANDBOX_NAME is required (the sandbox group, e.g. built-in / custom)}"
: "${SANDBOX_TOKEN:?SANDBOX_TOKEN is required (the scoped sandbox access token)}"

exec python -m hass_client.sandbox \
  --name "${SANDBOX_NAME}" \
  --url "${SANDBOX_URL:-stdio://}" \
  --token "${SANDBOX_TOKEN}" \
  --log-level "${SANDBOX_LOG_LEVEL:-INFO}"
