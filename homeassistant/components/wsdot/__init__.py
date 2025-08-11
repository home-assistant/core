"""The wsdot component."""

from dataclasses import dataclass

import wsdot as wsdot_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]


@dataclass
class WsdotRuntimeData:
    """WSDOT API handlers."""

    wsdot_travel_times: wsdot_api.WsdotTravelTimes


type WsdotConfigEntry = ConfigEntry[WsdotRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up wsdot as config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
