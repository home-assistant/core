"""The qbittorrent component."""
import asyncio
import logging

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException

import voluptuous as vol

from homeassistant.components.poolsense import PLATFORMS
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
    CONF_CATEGORIES,
    DEFAULT_NAME,
    DOMAIN,
    SENSOR_TYPE_ACTIVE_TORRENTS,
    SENSOR_TYPE_COMPLETED_TORRENTS,
    SENSOR_TYPE_CURRENT_STATUS,
    SENSOR_TYPE_DOWNLOAD_SPEED,
    SENSOR_TYPE_DOWNLOADING_TORRENTS,
    SENSOR_TYPE_INACTIVE_TORRENTS,
    SENSOR_TYPE_PAUSED_TORRENTS,
    SENSOR_TYPE_RESUMED_TORRENTS,
    SENSOR_TYPE_SEEDING_TORRENTS,
    SENSOR_TYPE_TOTAL_TORRENTS,
    SENSOR_TYPE_UPLOAD_SPEED,
    TRIM_SIZE,
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
        await client.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err
