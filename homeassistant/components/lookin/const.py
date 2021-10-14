"""The lookin integration constants."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN = "lookin"


LOGGER = logging.getLogger(__name__)

DEVICES: Final = "devices"
LOOKIN_DEVICE: Final = "lookin_device"
PROTOCOL: Final = "protocol"
METEO_COORDINATOR: Final = "meteo_coordinator"

PLATFORMS: Final = ["sensor", "climate", "media_player", "light", "vacuum", "fan"]
