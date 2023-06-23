"""The Hunter Hydrawise integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, PASSWORD, USERNAME
from .coordinator import HydrawiseDataUpdateCoordinator
from .hydrawiser import Hydrawiser
from .pydrawise.exceptions import Error

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hunter Hydrawise from a config entry."""
    username = entry.data[USERNAME]
    password = entry.data[PASSWORD]
    try:
        hydrawise = await hass.async_add_executor_job(Hydrawiser, username, password)
    except Error as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", str(ex))
        return False

    if not await hydrawise.async_update_controllers():
        LOGGER.error("Failed to fetch Hydrawise data")
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = HydrawiseDataUpdateCoordinator(hass, hydrawise)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
