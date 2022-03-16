"""Constants for the update component."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "update"

# Bitfield of features supported by the update entity
SUPPORT_SPECIFIC_VERSION: Final = 1
SUPPORT_PROGRESS: Final = 2
SUPPORT_BACKUP: Final = 4

SERVICE_INSTALL: Final = "install"
SERVICE_SKIP: Final = "skip"

ATTR_BACKUP: Final = "backup"
ATTR_CURRENT_VERSION: Final = "current_version"
ATTR_IN_PROGRESS: Final = "in_progress"
ATTR_LATEST_VERSION: Final = "latest_version"
ATTR_RELEASE_SUMMARY: Final = "release_summary"
ATTR_RELEASE_URL: Final = "release_url"
ATTR_SKIPPED_VERSION: Final = "skipped_version"
ATTR_TITLE: Final = "title"
ATTR_VERSION: Final = "version"
