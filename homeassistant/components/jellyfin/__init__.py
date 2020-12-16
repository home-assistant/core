"""The Jellyfin integration."""
import logging

from jellyfin_apiclient_python import Jellyfin
import voluptuous as vol

from homeassistant.components.jellyfin.config_flow import authenticate, setup_client
from homeassistant.components.jellyfin.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

from .const import DATA_CLIENT, DOMAIN  # pylint:disable=unused-import


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the jellyfin component."""
    hass.data.setdefault(DOMAIN, {})

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up jellyfin from a config entry."""

    jellyfin = Jellyfin()
    setup_client(jellyfin)

    url = entry.data.get(CONF_URL)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    connected = await hass.async_add_executor_job(
        authenticate, jellyfin.get_client(), url, username, password
    )

    if connected:
        _LOGGER.debug("Adding API to domain data storage for entry %s", entry.entry_id)

        client = jellyfin.get_client()

        hass.data[DOMAIN][entry.entry_id] = {DATA_CLIENT: client}

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id)

    return True