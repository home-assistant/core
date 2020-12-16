"""The Jellyfin integration."""
import logging

import voluptuous as vol

from homeassistant.components.jellyfin.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.jellyfin.const import DATA_CLIENT, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the jellyfin component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Jellyfin from a config entry."""

    try:
        client = await validate_input(hass, entry.data)
    except CannotConnect:
        _LOGGER.error("Cannot connect to Jellyfin server")
        return False
    except InvalidAuth:
        _LOGGER.error("Failed to login to Jellyfin server")
        return False
    except Exception:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Unexpected exception occured while setting up Jellyfin server"
        )
        return False
    else:
        _LOGGER.debug("Adding API to domain data storage for entry %s", entry.entry_id)

        hass.data[DOMAIN][entry.entry_id] = {DATA_CLIENT: client}

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
