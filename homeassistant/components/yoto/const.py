"""Constants for the Yoto integration."""

from datetime import timedelta
from enum import StrEnum
import logging

DOMAIN = "yoto"

LOGGER = logging.getLogger(__package__)

YOTO_AUDIENCE = "https://api.yotoplay.com"

YOTO_SCOPES = [
    "offline_access",
    "family:view",
    "family:devices:view",
    "family:devices:control",
    "family:devices:manage",
    "family:library:view",
    "user:content:view",
    "user:icons:manage",
]

SCAN_INTERVAL = timedelta(minutes=5)
STATUS_PUSH_INTERVAL = timedelta(seconds=60)

MANUFACTURER = "Yoto"


class SleepTimerMode(StrEnum):
    """When the sleep timer stops playback."""

    DURATION = "duration"
    END_OF_TRACK = "end_of_track"
