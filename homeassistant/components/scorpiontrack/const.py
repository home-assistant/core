"""Constants for the ScorpionTrack integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "scorpiontrack"
DEFAULT_NAME = "ScorpionTrack"
MANUFACTURER = "ScorpionTrack"

CONF_SHARE_TOKEN = "share_token"

ACTIVE_SCAN_INTERVAL = timedelta(seconds=15)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
)
