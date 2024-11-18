"""The lookin integration constants."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform

MODEL_NAMES: Final = ["LOOKin Remote", "LOOKin Remote", "LOOKin Remote2"]

DOMAIN: Final = "lookin"
PLATFORMS: Final = [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.MEDIA_PLAYER,
    Platform.SENSOR,
]


TYPE_TO_PLATFORM = {
    "01": Platform.MEDIA_PLAYER,
    "02": Platform.MEDIA_PLAYER,
    "03": Platform.LIGHT,
    "EF": Platform.CLIMATE,
}

NEVER_TIME = -120.0  # Time that will never match time.monotonic()
ACTIVE_UPDATES_INTERVAL = 4  # Consider active for 4x the update interval
METEO_UPDATE_INTERVAL = timedelta(minutes=5)
REMOTE_UPDATE_INTERVAL = timedelta(seconds=60)
POLLING_FALLBACK_SECONDS = (
    max(REMOTE_UPDATE_INTERVAL, METEO_UPDATE_INTERVAL).total_seconds()
    * ACTIVE_UPDATES_INTERVAL
)
