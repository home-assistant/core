"""Constants for Folder watcher."""

from homeassistant.const import Platform

CONF_FOLDER = "folder"
CONF_PATTERNS = "patterns"
DEFAULT_PATTERN = "*"
DOMAIN = "folder_watcher"

PLATFORMS = [Platform.EVENT]
