from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers.typing import ConfigType


@dataclass(slots=True)
class LocationServiceInfo(BaseServiceInfo):
    """Information about a location service."""

    longitude: float
    latitude: float

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the location component."""
    return True