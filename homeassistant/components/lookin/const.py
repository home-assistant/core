"""The lookin integration constants."""
from __future__ import annotations

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
