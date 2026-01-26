"""Constants for the Tag integration."""

from __future__ import annotations

import logging
from typing import TypedDict

DEVICE_ID = "device_id"
DOMAIN = "tag"
EVENT_TAG_SCANNED = "tag_scanned"
TAG_ID = "tag_id"
DEFAULT_NAME = "Tag"
LOGGER = logging.getLogger(__package__)


class TagScannedEventData(TypedDict):
    """Data for tag_scanned event."""

    tag_id: str
    name: str | None
    device_id: str | None
