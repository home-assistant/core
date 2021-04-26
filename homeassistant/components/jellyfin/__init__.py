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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Jellyfin from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        client = await validate_input(hass, entry.data)
    except CannotConnect as ex:
        raise ConfigEntryNotReady("Cannot connect to Jellyfin server") from ex
    except InvalidAuth as ex:
        raise ConfigEntryAuthFailed("Failed to login to Jellyfin server") from ex
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.exception(ex)
        raise ConfigEntryNotReady(
            "Unexpected exception occurred while setting up Jellyfin server"
        ) from ex
    else:
        _LOGGER.debug("Adding API to domain data storage for entry %s", entry.entry_id)

        hass.data[DOMAIN][entry.entry_id] = {DATA_CLIENT: client}

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
