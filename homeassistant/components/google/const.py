"""Constants for google integration."""
from __future__ import annotations

from enum import Enum

DOMAIN = "google"
DEVICE_AUTH_IMPL = "device_auth"

CONF_CALENDAR_ACCESS = "calendar_access"
DATA_CALENDARS = "calendars"
DATA_SERVICE = "service"
DATA_CONFIG = "config"
DATA_STORE = "store"


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


DEFAULT_FEATURE_ACCESS = FeatureAccess.read_write


EVENT_DESCRIPTION = "description"
EVENT_END_DATE = "end_date"
EVENT_END_DATETIME = "end_date_time"
EVENT_IN = "in"
EVENT_IN_DAYS = "days"
EVENT_IN_WEEKS = "weeks"
EVENT_LOCATION = "location"
EVENT_START_DATE = "start_date"
EVENT_START_DATETIME = "start_date_time"
EVENT_SUMMARY = "summary"
EVENT_TYPES_CONF = "event_types"
