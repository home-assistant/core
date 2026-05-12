"""Component constants."""

from homeassistant.const import Platform

CONF_BACKFILL_DAYS = "backfill_days"
DEFAULT_BACKFILL_DAYS = 365
DEFAULT_RECENT_SYNC_DAYS = 7
DOMAIN = "ohme"
PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]
