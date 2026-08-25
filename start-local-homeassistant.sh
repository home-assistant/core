#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${HA_VENV_DIR:-${ROOT_DIR}/.venv}"
CONFIG_DIR="${HA_CONFIG_DIR:-${ROOT_DIR}/.ha-marstek-config}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  echo "Missing Python at ${VENV_DIR}/bin/python" >&2
  exit 1
fi

mkdir -p "${CONFIG_DIR}"

export PATH="${VENV_DIR}/bin:${PATH}"
if [[ -z "${PYTHONMALLOC:-}" ]] && "${VENV_DIR}/bin/python" -c "import mimalloc" 2>/dev/null; then
  export PYTHONMALLOC="mimalloc"
fi

cd "${ROOT_DIR}"
exec "${VENV_DIR}/bin/python" -m homeassistant --config "${CONFIG_DIR}" "$@"
