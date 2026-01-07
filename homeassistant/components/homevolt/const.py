"""Constants for the Homevolt integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import HomevoltDataUpdateCoordinator

DOMAIN = "homevolt"
MANUFACTURER = "Homevolt"
SCAN_INTERVAL = timedelta(seconds=15)
type HomevoltConfigEntry = ConfigEntry["HomevoltDataUpdateCoordinator"]
