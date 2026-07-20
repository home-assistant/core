"""Constants for the update component."""

from enum import IntFlag, StrEnum
from typing import Final

DOMAIN: Final = "update"


class UpdateEntityStateAttribute(StrEnum):
    """State attributes for update entities."""

    AUTO_UPDATE = "auto_update"
    DISPLAY_PRECISION = "display_precision"
    INSTALLED_VERSION = "installed_version"
    IN_PROGRESS = "in_progress"
    LATEST_VERSION = "latest_version"
    RELEASE_SUMMARY = "release_summary"
    RELEASE_URL = "release_url"
    SKIPPED_VERSION = "skipped_version"
    TITLE = "title"
    UPDATE_PERCENTAGE = "update_percentage"


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
ATTR_DISPLAY_PRECISION: Final = "display_precision"
ATTR_INSTALLED_VERSION: Final = "installed_version"
ATTR_IN_PROGRESS: Final = "in_progress"
ATTR_LATEST_VERSION: Final = "latest_version"
ATTR_RELEASE_SUMMARY: Final = "release_summary"
ATTR_RELEASE_URL: Final = "release_url"
ATTR_SKIPPED_VERSION: Final = "skipped_version"
ATTR_TITLE: Final = "title"
ATTR_UPDATE_PERCENTAGE: Final = "update_percentage"
ATTR_VERSION: Final = "version"
