"""Constants for the EPH Controls Ember integration."""

import logging
from typing import Final

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)
DOMAIN: Final = "ephember"
PLATFORMS = [Platform.CLIMATE]


def signal_zone_update(entry_id: str, zone_id: str) -> str:
    """Dispatcher signal sent when a live update for a zone arrives."""
    return f"{DOMAIN}_{entry_id}_{zone_id}_update"
