"""The gogogate2 component."""
from homeassistant.components.cover import DOMAIN as COVER_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .common import get_data_update_coordinator


async def async_setup(hass: HomeAssistant, base_config: dict) -> bool:
    """Set up for Gogogate2 controllers."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Do setup of Gogogate2."""
    data_update_coordinator = get_data_update_coordinator(hass, config_entry)
    await data_update_coordinator.async_refresh()

    if not data_update_coordinator.last_update_success:
        raise ConfigEntryNotReady()

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, COVER_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Gogogate2 config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_unload(config_entry, COVER_DOMAIN)
    )

    return True
