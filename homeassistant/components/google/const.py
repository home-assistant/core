"""Constants for google integration."""
from __future__ import annotations

from enum import Enum

DOMAIN = "google"
DEVICE_AUTH_IMPL = "device_auth"

CONF_CALENDAR_ACCESS = "calendar_access"
DATA_CALENDARS = "calendars"
DATA_SERVICE = "service"
DATA_CONFIG = "config"

DISCOVER_CALENDAR = "google_discover_calendar"


class FeatureAccess(Enum):
    """Class to represent different access scopes."""

    read_only = "https://www.googleapis.com/auth/calendar.readonly"
    read_write = "https://www.googleapis.com/auth/calendar"

    def __init__(self, scope: str) -> None:
        """Init instance."""
        self._scope = scope

    @property
    def scope(self) -> str:
        """Google calendar scope for the feature."""
        return self._scope
