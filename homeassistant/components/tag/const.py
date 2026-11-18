"""Constants for the Tag integration."""

from enum import StrEnum
import logging

DEVICE_ID = "device_id"
DOMAIN = "tag"
EVENT_TAG_SCANNED = "tag_scanned"
TAG_ID = "tag_id"
DEFAULT_NAME = "Tag"
LOGGER = logging.getLogger(__package__)


class TagEntityStateAttribute(StrEnum):
    """State attributes for tag entities."""

    LAST_SCANNED_BY_DEVICE_ID = "last_scanned_by_device_id"
    TAG_ID = "tag_id"
