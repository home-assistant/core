"""The lookin integration constants."""
from __future__ import annotations

import logging
from typing import Final

DOMAIN = "lookin"

LOGGER = logging.getLogger(__name__)

PLATFORMS: Final = ["sensor", "climate", "media_player", "light", "vacuum", "fan"]
