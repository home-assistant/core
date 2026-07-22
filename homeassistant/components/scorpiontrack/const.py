"""Constants for the ScorpionTrack integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "scorpiontrack"
DEFAULT_NAME = "ScorpionTrack"
MANUFACTURER = "ScorpionTrack"

CONF_SHARE_TOKEN = "share_token"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)

PLATFORMS: tuple[Platform, ...] = (Platform.DEVICE_TRACKER,)
