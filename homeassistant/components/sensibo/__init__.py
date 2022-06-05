"""The sensibo component."""
from __future__ import annotations

from pysensibo.exceptions import AuthenticationError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import SensiboDataUpdateCoordinator
from .util import NoDevicesError, NoUsernameError, async_validate_api


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Sensibo from a config entry."""

    coordinator = SensiboDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Sensibo config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    # Change entry unique id from api_key to username
    if entry.version == 1:
        api_key = entry.data[CONF_API_KEY]

        try:
            new_unique_id = await async_validate_api(hass, api_key)
        except (AuthenticationError, ConnectionError, NoDevicesError, NoUsernameError):
            return False

        entry.version = 2

        LOGGER.debug("Migrate Sensibo config entry unique id to %s", new_unique_id)
        hass.config_entries.async_update_entry(
            entry,
            unique_id=new_unique_id,
        )

    return True
