"""Constants for the persistent notification integration."""

from datetime import datetime
from enum import StrEnum
from typing import Final, TypedDict

from homeassistant.util.signal_type import SignalType

DOMAIN = "persistent_notification"

ATTR_CREATED_AT: Final = "created_at"
ATTR_MESSAGE: Final = "message"
ATTR_NOTIFICATION_ID: Final = "notification_id"
ATTR_TITLE: Final = "title"
ATTR_STATUS: Final = "status"


class Notification(TypedDict):
    """Persistent notification."""

    created_at: datetime
    message: str
    notification_id: str
    title: str | None


class UpdateType(StrEnum):
    """Persistent notification update type."""

    CURRENT = "current"
    ADDED = "added"
    REMOVED = "removed"
    UPDATED = "updated"


SIGNAL_PERSISTENT_NOTIFICATIONS_UPDATED = SignalType[
    UpdateType, dict[str, Notification]
]("persistent_notifications_updated")
