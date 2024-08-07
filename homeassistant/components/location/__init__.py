"""Location based auto discovery."""

from dataclasses import dataclass

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers.typing import ConfigType

CONFIG_SCHEMA = vol.Schema({})


@dataclass(slots=True)
class LocationServiceInfo(BaseServiceInfo):
    """Information about a location service."""

    longitude: float
    latitude: float


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the location component."""
    return True
