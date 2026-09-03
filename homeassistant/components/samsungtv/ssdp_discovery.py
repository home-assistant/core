"""SSDP discovery helpers for Samsung TV."""

from urllib.parse import urlparse

from homeassistant.components.ssdp import async_get_discovery_info_by_st
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import (
    CONF_SSDP_MAIN_TV_AGENT_LOCATION,
    CONF_SSDP_RENDERING_CONTROL_LOCATION,
    UPNP_SVC_MAIN_TV_AGENT,
    UPNP_SVC_RENDERING_CONTROL,
)
from .coordinator import SamsungTVConfigEntry


async def async_update_ssdp_locations(
    hass: HomeAssistant, entry: SamsungTVConfigEntry
) -> None:
    """Update ssdp locations from discovery cache."""
    updates = {}
    for ssdp_st, key in (
        (UPNP_SVC_RENDERING_CONTROL, CONF_SSDP_RENDERING_CONTROL_LOCATION),
        (UPNP_SVC_MAIN_TV_AGENT, CONF_SSDP_MAIN_TV_AGENT_LOCATION),
    ):
        for discovery_info in await async_get_discovery_info_by_st(hass, ssdp_st):
            location = discovery_info.ssdp_location
            host = urlparse(location).hostname
            if host == entry.data[CONF_HOST]:
                updates[key] = location
                break

    if updates:
        hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})
