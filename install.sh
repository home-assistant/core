#!/usr/bin/env bash
# Installer for ha-claude: Home Assistant MCP plugin for Claude Code
set -euo pipefail

PLUGIN_NAME="ha-claude"
PLUGIN_PACKAGE="@rygwdn/ha-claude"

# ── helpers ────────────────────────────────────────────────────────────────

info()    { printf '\033[1;34m[ha-claude]\033[0m %s\n' "$*"; }
success() { printf '\033[1;32m[ha-claude]\033[0m %s\n' "$*"; }
warn()    { printf '\033[1;33m[ha-claude]\033[0m %s\n' "$*" >&2; }
die()     { printf '\033[1;31m[ha-claude]\033[0m %s\n' "$*" >&2; exit 1; }

# ── install claude-code if missing ─────────────────────────────────────────

install_claude() {
    info "Claude Code not found — installing..."

    if command -v npm &>/dev/null; then
        npm install -g @anthropic-ai/claude-code
        return
    fi

    if command -v brew &>/dev/null; then
        brew install claude
        return
    fi

    die "Neither npm nor Homebrew found. Install Node.js (https://nodejs.org) or Homebrew (https://brew.sh), then re-run this script."
}

if ! command -v claude &>/dev/null; then
    install_claude
fi

# Verify installation succeeded
command -v claude &>/dev/null || die "Claude Code installation failed. Install manually: https://docs.anthropic.com/claude-code"

# ── install the plugin ─────────────────────────────────────────────────────

info "Installing ${PLUGIN_NAME} MCP plugin..."

# Remove any previous install so this is idempotent
claude mcp remove "${PLUGIN_NAME}" --scope user 2>/dev/null || true

claude mcp add "${PLUGIN_NAME}" \
    --scope user \
    -- npx -y "${PLUGIN_PACKAGE}"

success "Done! ${PLUGIN_NAME} is installed."
info "Restart Claude Code (or start a new session) for the plugin to take effect."
