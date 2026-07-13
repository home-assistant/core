#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$SCRIPT_DIR"
PLUGIN_NAME="super-pmo-agent"
DEST_ROOT="${1:-$HOME}"
DEST_PLUGIN_DIR="$DEST_ROOT/plugins/$PLUGIN_NAME"
DEST_MARKETPLACE_DIR="$DEST_ROOT/.agents/plugins"
DEST_MARKETPLACE="$DEST_MARKETPLACE_DIR/marketplace.json"

mkdir -p "$(dirname "$DEST_PLUGIN_DIR")" "$DEST_MARKETPLACE_DIR"
rm -rf "$DEST_PLUGIN_DIR"
cp -R "$PLUGIN_ROOT" "$DEST_PLUGIN_DIR"

python3 - "$DEST_MARKETPLACE" "$PLUGIN_NAME" <<'PY'
import json
import sys
from pathlib import Path

marketplace = Path(sys.argv[1])
plugin_name = sys.argv[2]
entry = {
    "name": plugin_name,
    "source": {"source": "local", "path": f"./plugins/{plugin_name}"},
    "policy": {"installation": "INSTALLED_BY_DEFAULT", "authentication": "ON_USE"},
    "category": "Productivity",
}
if marketplace.exists():
    data = json.loads(marketplace.read_text())
else:
    data = {"name": "local-plugins", "interface": {"displayName": "Local Plugins"}, "plugins": []}
plugins = [plugin for plugin in data.get("plugins", []) if plugin.get("name") != plugin_name]
plugins.append(entry)
data["plugins"] = plugins
data.setdefault("interface", {}).setdefault("displayName", "Local Plugins")
data.setdefault("name", "local-plugins")
marketplace.write_text(json.dumps(data, indent=2) + "\n")
PY

echo "Installed $PLUGIN_NAME to $DEST_PLUGIN_DIR"
echo "Updated $DEST_MARKETPLACE"
