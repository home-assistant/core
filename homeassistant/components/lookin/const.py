"""The lookin integration constants."""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

MODEL_NAMES: Final = ["LOOKin Remote", "LOOKin Remote", "LOOKin Remote2"]

DOMAIN: Final = "lookin"
PLATFORMS: Final = [Platform.CLIMATE, Platform.SENSOR, Platform.MEDIA_PLAYER]
  