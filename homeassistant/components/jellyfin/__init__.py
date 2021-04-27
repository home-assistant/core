"""The Jellyfin integration."""
import logging

from homeassistant.components.jellyfin.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.jellyfin.const import DATA_CLIENT, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jellyfin from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        client = await validate_input(hass, dict(entry.data))
    except CannotConnect as ex:
        raise ConfigEntryNotReady("Cannot connect to Jellyfin server") from ex
    except InvalidAuth as ex:
        _LOGGER.exception("Failed to login to Jellyfin server: %s", ex)
        return False
    except Exception as ex:  # pylint: disable=broad-except
        _LOGGER.exception(
            "Unexpected exception occurred while setting up Jellyfin server: %s", ex
        )
        return False
    else:
        _LOGGER.debug("Adding API to domain data storage for entry %s", entry.entry_id)

        hass.data[DOMAIN][entry.entry_id] = {DATA_CLIENT: client}

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
