#!/bin/bash
# Run Home Assistant from this worktree with the main config

WORKTREE_DIR="/workspaces/home-assistant-dev.worktrees/copilot-worktree-2026-01-20T21-02-42"
CONFIG_DIR="/workspaces/home-assistant-dev/config"

echo "🚀 Starting Home Assistant..."
echo "   Code from: $WORKTREE_DIR"
echo "   Config from: $CONFIG_DIR"
echo ""

cd "$WORKTREE_DIR" || exit 1
python -m homeassistant -c "$CONFIG_DIR"
