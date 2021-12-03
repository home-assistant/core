"""The lookin integration constants."""
from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "lookin"
PLATFORMS: Final = [Platform.SENSOR, Platform.CLIMATE]
