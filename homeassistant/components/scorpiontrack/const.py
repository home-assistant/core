"""Constants for the ScorpionTrack integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "scorpiontrack"
DEFAULT_NAME = "ScorpionTrack"
SHARE_DEVICE_DEFAULT_NAME = "ScorpionTrack Share"
MANUFACTURER = "ScorpionTrack"

CONF_SHARE_TOKEN = "share_token"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=2)
STALE_POSITION_THRESHOLD = timedelta(hours=24)

PLATFORMS: tuple[Platform, ...] = (Platform.DEVICE_TRACKER,)
