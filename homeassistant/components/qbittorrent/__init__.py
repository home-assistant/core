"""The qbittorrent component."""
import asyncio
import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

# from homeassistant.components.qbittorrent import PLATFORMS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MONITORED_VARIABLES,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    DATA_RATE_KILOBYTES_PER_SECOND,
    STATE_IDLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
)

PLATFORMS = ["sensor"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Qbittorrent component."""
    # Make sure coordinator is initialized.
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Qbittorrent from a config entry."""
    try:
        client = Client(entry.data[CONF_URL])
        client.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err
    return True
