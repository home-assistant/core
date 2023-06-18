"""The Hunter Hydrawise integration."""
from __future__ import annotations

from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import ACCESS_TOKEN, DOMAIN, LOGGER, SCAN_INTERVAL
from .coordinator import HydrawiseDataUpdateCoordinator
from .hydrawiser import Hydrawiser

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hunter Hydrawise from a config entry."""
    access_token = entry.data[ACCESS_TOKEN]
    try:
        hydrawise = await hass.async_add_executor_job(Hydrawiser, access_token)
    except (ConnectTimeout, HTTPError) as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        return False

    if not hydrawise.controllers:
        LOGGER.error("Failed to fetch Hydrawise data")
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = HydrawiseDataUpdateCoordinator(
        hass, hydrawise, SCAN_INTERVAL
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
