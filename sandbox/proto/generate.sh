#!/usr/bin/env bash
# Regenerate the checked-in protobuf gencode for both mirrors.
#
# Core has no build-time protoc and grpcio-tools is NOT a project dependency
# (installing it into the main venv would bump protobuf past the pinned
# 6.32.0). So this script bootstraps a throwaway, isolated venv pinned to the
# runtime's protobuf and generates into both no-cross-import mirrors:
#
#   homeassistant/components/sandbox/_proto/sandbox_pb2.py(+.pyi)
#   sandbox/hass_client/hass_client/_proto/sandbox_pb2.py(+.pyi)
#
# Usage (from the repo root):  sandbox/proto/generate.sh
#
# After running, `git diff --exit-code` the two _pb2 paths must be clean — a
# dirty diff means the checked-in gencode drifted from the .proto.

set -euo pipefail

# Resolve the repo root from this script's location so it works from anywhere.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

PROTO_DIR="sandbox/proto"
HA_DEST="homeassistant/components/sandbox/_proto"
CLIENT_DEST="sandbox/hass_client/hass_client/_proto"

# pinned to match homeassistant/package_constraints.txt; grpcio-tools==1.80.0
# (resolved by uv) emits gencode requiring protobuf >= 6.31.1, satisfied here.
PROTOBUF_PIN="protobuf==6.32.0"
VENV_DIR="$(mktemp -d -t sandbox_protogen_XXXXXX)"
trap 'rm -rf "${VENV_DIR}"' EXIT

echo "Bootstrapping isolated protogen venv at ${VENV_DIR} ..."
uv venv "${VENV_DIR}" --python 3.14 >/dev/null
uv pip install --python "${VENV_DIR}" "${PROTOBUF_PIN}" grpcio-tools mypy-protobuf >/dev/null

for DEST in "${HA_DEST}" "${CLIENT_DEST}"; do
  mkdir -p "${DEST}"
  touch "${DEST}/__init__.py"
  echo "Generating into ${DEST} ..."
  "${VENV_DIR}/bin/python" -m grpc_tools.protoc \
    -I "${PROTO_DIR}" \
    --python_out="${DEST}" \
    --pyi_out="${DEST}" \
    "${PROTO_DIR}/sandbox.proto"
done

echo "Done. Verify with: git diff --exit-code ${HA_DEST} ${CLIENT_DEST}"
