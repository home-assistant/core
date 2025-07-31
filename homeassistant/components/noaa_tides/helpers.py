"""Helpers for NOAA Tides integration."""

from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import UNIT_SYSTEMS


def get_station_unique_id(station_id: str) -> str:
    """Convert a station ID to a unique ID."""
    return f"{station_id.lower()}"


def get_default_unit_system(hass: HomeAssistant | None = None) -> str:
    """Return the default unit system."""
    if hass is not None and hass.config.units is US_CUSTOMARY_SYSTEM:
        return UNIT_SYSTEMS[0]
    return UNIT_SYSTEMS[1]
