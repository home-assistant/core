#!/usr/bin/env bash
# Drift guard for the hand-mirrored sandbox wire modules.
#
# channel.py, codec_protobuf.py, messages.py and the checked-in protobuf
# gencode (_proto/sandbox_pb2.py + .pyi) are maintained as byte-identical
# copies in two places:
#
#   homeassistant/components/sandbox/<file>        (HA Core integration side)
#   sandbox/hass_client/hass_client/<file>         (sandbox runtime side)
#
# They are duplicated rather than shared because the HA Core integration must
# not import from ``hass_client`` and ``hass_client`` must not import from
# ``homeassistant.components.*``. This guard fails if any pair diverges, so the
# "edit both copies" rule is enforced instead of trusted.
#
# Unlike the proto regeneration guard (check_drift.sh, which re-runs protoc to
# compare against sandbox.proto) this is a plain ``diff`` with no external
# tooling, so it is wired as a regular every-commit prek hook that fires
# whenever a mirrored file changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

HA_DIR="homeassistant/components/sandbox"
CLIENT_DIR="sandbox/hass_client/hass_client"
MIRRORED_FILES=(
  channel.py
  codec_protobuf.py
  messages.py
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
