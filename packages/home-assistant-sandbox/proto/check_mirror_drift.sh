#!/usr/bin/env bash
# Keep wire modules identical on both sides of the process boundary.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
cd "${REPO_ROOT}"

HA_DIR="homeassistant/components/sandbox"
CLIENT_DIR="packages/home-assistant-sandbox/homeassistant_sandbox"
MIRRORED_FILES=(
  channel.py
  codec_protobuf.py
  messages.py
  entry_sync.py
  _proto/sandbox_pb2.py
  _proto/sandbox_pb2.pyi
)

status=0
for file in "${MIRRORED_FILES[@]}"; do
  if ! diff -u "${HA_DIR}/${file}" "${CLIENT_DIR}/${file}"; then
    echo
    echo "ERROR: ${file} differs between the two mirrors."
    status=1
  fi
done

if [ "${status}" -ne 0 ]; then
  echo
  echo "The sandbox wire modules are hand-mirrored and must stay byte-identical."
  echo "Apply the same change to BOTH copies:"
  echo "  ${HA_DIR}/<file>"
  echo "  ${CLIENT_DIR}/<file>"
  exit 1
fi

echo "sandbox mirror drift guard: all mirrored wire modules match."
