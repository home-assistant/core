#!/usr/bin/env bash
# Drift guard for the checked-in sandbox_v2 protobuf gencode.
#
# Regenerates the _pb2 mirrors from sandbox_v2.proto (via generate.sh, which
# bootstraps its own throwaway venv — grpcio-tools is deliberately NOT a
# project dependency, since it would bump protobuf past the pinned 6.32.0)
# and fails if the result differs from what is checked in.
#
# Degrades gracefully: if `uv` (needed to build the isolated protoc venv) is
# not on PATH, it skips with a notice and exits 0 rather than blocking the
# commit. This is why it is wired as a MANUAL-stage prek hook
# (`prek run --hook-stage manual sandbox-v2-proto-drift`) / dedicated CI lane,
# not an every-commit hook.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

if ! command -v uv >/dev/null 2>&1; then
  echo "sandbox_v2 proto drift guard: 'uv' not found — skipping (install uv to run)."
  exit 0
fi

HA_DEST="homeassistant/components/sandbox_v2/_proto"
CLIENT_DEST="sandbox_v2/hass_client/hass_client/_proto"

bash "${SCRIPT_DIR}/generate.sh" >/dev/null

if ! git diff --exit-code -- "${HA_DEST}" "${CLIENT_DEST}"; then
  echo
  echo "ERROR: checked-in protobuf gencode is out of date with sandbox_v2.proto."
  echo "Run 'sandbox_v2/proto/generate.sh' and commit the regenerated _pb2 files."
  exit 1
fi

echo "sandbox_v2 proto drift guard: gencode matches sandbox_v2.proto."
