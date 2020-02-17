"""The totalconnect component."""
import asyncio
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from total_connect_client import TotalConnectClient

from pprint import pprint

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["alarm_control_panel", "binary_sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Setup from existing/saved configuration."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True
        
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    client = TotalConnectClient.TotalConnectClient(username, password)

    if client.token is False:
        _LOGGER.error("TotalConnect authentication failed")
        return False

    hass.data[DOMAIN] = TotalConnectSystem(username, password, client)

    for platform in PLATFORMS:
        hass.async_create_task(discovery.async_load_platform(hass, platform, DOMAIN, {}, config))

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Setup upon config entry in user interface."""

    _LOGGER.info("TotalConnect async_setup_entry")

    conf = entry.data
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)
    client = TotalConnectClient.TotalConnectClient(username, password)

    if client.token is False:
        _LOGGER.error("TotalConnect authentication failed")
        return False

    hass.data[DOMAIN] = TotalConnectSystem(username, password, client)

    for platform in PLATFORMS:
        hass.async_create_task(discovery.async_load_platform(hass, platform, DOMAIN, {}, entry))

    #Pretty sure we don't do this because the component itself doesn't need the configuration data
#    for component in PLATFORMS:
#        hass.async_create_task(
#            hass.config_entries.async_forward_entry_setup(entry, component)
#        )

    return True



class TotalConnectSystem:
    """TotalConnect System class."""

    def __init__(self, username, password, client):
        """Initialize the TotalConnect system."""
        self._username = username
        self._password = password
        self.client = client
