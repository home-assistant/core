"""The openevse component."""
import logging

import openevsewifi
from openevsewifi import InvalidAuthentication
from requests import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up is called when Home Assistant is loading our component."""
    config_entry.add_update_listener(update_listener)
    await hass.config_entries.async_forward_entry_setup(config_entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update listener."""

    _LOGGER.debug("Attempting to reload entities from the %s integration", DOMAIN)

    if config_entry.data == config_entry.options:
        _LOGGER.debug("No changes detected not reloading entities")
        return

    new_data = config_entry.options.copy()

    hass.config_entries.async_update_entry(
        entry=config_entry,
        data=new_data,
    )

    await hass.config_entries.async_reload(config_entry.entry_id)


def test_connection(host: str, username: str, password: str) -> tuple:
    """Test connection to charger."""
    charger = openevsewifi.Charger(host, username=username, password=password)
    try:
        charger.status
    except RequestException:
        return (False, "cannot_connect")
    except InvalidAuthentication:
        return (False, "invalid_auth")
    return (True, "")
