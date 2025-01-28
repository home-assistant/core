"""B-Route Smart Meter Integration.

This file is typically used to set up the integration at runtime:
 - async_setup_entry: Called when user adds the integration
 - async_unload_entry: Called to remove it

"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_RETRY_COUNT,
    CONF_ROUTE_B_ID,
    CONF_ROUTE_B_PWD,
    CONF_SERIAL_PORT,
    DEFAULT_RETRY_COUNT,
    DEFAULT_SERIAL_PORT,
    DOMAIN,
)
from .coordinator import BRouteDataCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up B-Route meter from a config entry."""
    data = entry.data
    route_b_id = data[CONF_ROUTE_B_ID]
    route_b_pwd = data[CONF_ROUTE_B_PWD]
    serial_port = data.get(CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT)
    retry_count = data.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT)

    coordinator = BRouteDataCoordinator(
        hass,
        route_b_id,
        route_b_pwd,
        serial_port,
        retry_count=retry_count,
    )
    entry.runtime_data = coordinator
    hass.data.setdefault(DOMAIN, {})

    # Store the config entry data for later usage
    hass.data[DOMAIN][entry.entry_id] = {}

    # Forward the setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
