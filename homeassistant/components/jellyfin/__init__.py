"""The Jellyfin integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .config_flow import CannotConnect, InvalidAuth, create_client, validate_input
from .const import DATA_CLIENT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Jellyfin from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    try:
        client = create_client()
        await validate_input(hass, dict(entry.data), client)
    except CannotConnect as ex:
        raise ConfigEntryNotReady("Cannot connect to Jellyfin server") from ex
    except InvalidAuth as ex:
        _LOGGER.exception("Failed to login to Jellyfin server: %s", ex)
        return False
    else:
        hass.data[DOMAIN][entry.entry_id] = {DATA_CLIENT: client}

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True
