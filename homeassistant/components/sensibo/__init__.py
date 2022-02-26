"""The sensibo component."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .config_flow import (
    CANNOT_CONNECT,
    INVALID_AUTH,
    NO_DEVICES,
    NO_USERNAME,
    async_validate_api,
)
from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import SensiboDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensibo from a config entry."""

    coordinator = SensiboDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Sensibo config entry."""
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
        return True
    return False


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # Change entry unique id from api_key to username
    if entry.version == 1:
        api_key = entry.data[CONF_API_KEY]
        new_unique_id = await async_validate_api(hass, api_key)
        if new_unique_id in [INVALID_AUTH, CANNOT_CONNECT, NO_DEVICES, NO_USERNAME]:
            return False

        LOGGER.debug("Migrate Sensibo config entry unique id to %s", new_unique_id)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=new_unique_id,
        )
        entry.version = 2

    return True
