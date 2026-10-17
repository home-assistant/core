#!/usr/bin/env bash
# Regenerate protobuf bindings and compare them with the checked-in copies.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "sandbox proto drift guard: 'uv' not found — skipping (install uv to run)."
  exit 0
fi

HA_DEST="homeassistant/components/sandbox/_proto"
CLIENT_DEST="sandbox/hass_client/hass_client/_proto"

bash "${SCRIPT_DIR}/generate.sh" >/dev/null

if ! git diff --exit-code -- "${HA_DEST}" "${CLIENT_DEST}"; then
  echo
  echo "ERROR: checked-in protobuf gencode is out of date with sandbox.proto."
  echo "Run 'sandbox/proto/generate.sh' and commit the regenerated _pb2 files."
  exit 1
fi

echo "sandbox proto drift guard: gencode matches sandbox.proto."
