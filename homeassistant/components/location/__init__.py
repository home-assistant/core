"""Location based auto discovery."""

from dataclasses import dataclass

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import BaseServiceInfo
from homeassistant.helpers import discovery_flow
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_locations

CONFIG_SCHEMA = vol.Schema({})


@dataclass(slots=True)
class LocationServiceInfo(BaseServiceInfo):
    """Information about a location service."""

    latitude: float
    longitude: float


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the location component."""
    location_definitions = await async_get_locations(hass)
    hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STARTED, lambda _: _discover(hass, location_definitions)
    )
    return True


async def _discover(
    hass: HomeAssistant, location_definitions: dict[str, list[str]]
) -> None:
    """Discover stuff."""
    applicable_regions = [
        "NL"
    ]  # This needs logic to be gathered dynamically based on coordinates

    location = LocationServiceInfo(hass.config.latitude, hass.config.longitude)

    for region in applicable_regions:
        if region in location_definitions:
            for domain in location_definitions[region]:
                discovery_flow.async_create_flow(
                    hass, domain, {"source": config_entries.SOURCE_LOCATION}, location
                )
