"""Constants for the update component."""

from __future__ import annotations

from enum import IntFlag
from typing import Final

DOMAIN: Final = "update"


class UpdateEntityFeature(IntFlag):
    """Supported features of the update entity."""

    INSTALL = 1
    SPECIFIC_VERSION = 2
    PROGRESS = 4
    BACKUP = 8
    RELEASE_NOTES = 16


SERVICE_INSTALL: Final = "install"
SERVICE_SKIP: Final = "skip"

ATTR_AUTO_UPDATE: Final = "auto_update"
ATTR_BACKUP: Final = "backup"
ATTR_INSTALLED_VERSION: Final = "installed_version"
ATTR_IN_PROGRESS: Final = "in_progress"
ATTR_LATEST_VERSION: Final = "latest_version"
ATTR_RELEASE_SUMMARY: Final = "release_summary"
ATTR_RELEASE_URL: Final = "release_url"
ATTR_SKIPPED_VERSION: Final = "skipped_version"
ATTR_TITLE: Final = "title"
ATTR_VERSION: Final = "version"
