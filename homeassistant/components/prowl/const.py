"""Constants for the Prowl Notification service."""

from homeassistant.const import Platform

DOMAIN = "prowl"
PLATFORMS = [Platform.NOTIFY]

ATTR_PRIORITY = "priority"
ATTR_URL = "url"

PRIORITY_MAP: dict[str, int] = {
    "very_low": -2,
    "moderate": -1,
    "normal": 0,
    "high": 1,
    "emergency": 2,
}
