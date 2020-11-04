"""The qbittorrent component."""
import asyncio
import logging
from aiohttp import client

from qbittorrent.client import Client, LoginRequired
from requests.exceptions import RequestException
import voluptuous as vol

# from homeassistant.components.qbittorrent import PLATFORMS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
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
    DATA_KEY_CLIENT,
    DATA_KEY_COORDINATOR,
    DATA_KEY_NAME,
    DOMAIN,
    SCAN_INTERVAL,
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
    name = "Qbittorrent"
    try:
        client = Client(entry.data[CONF_URL])
        client.login(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD])
    except LoginRequired:
        _LOGGER.error("Invalid authentication")
        return
    except RequestException as err:
        _LOGGER.error("Connection failed")
        raise PlatformNotReady from err

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            client.sync_main_data()
        except RequestException as err:
            raise UpdateFailed(f"Failed to communicating with API: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=name,
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_KEY_CLIENT: client,
        DATA_KEY_COORDINATOR: coordinator,
        DATA_KEY_NAME: name,
    }
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


class QBittorrentEntity(CoordinatorEntity):
    """Representation of a QBittorrent entity."""

    def __init__(self, client, coordinator, name, server_unique_id):
        """Initialize a QBittorrent entity."""
        super().__init__(coordinator)
        self.client = client
        self._name = name
        self._server_unique_id = server_unique_id

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return "mdi:cloud-download"

    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._server_unique_id)},
            "name": self._name,
            "manufacturer": "QBittorrent",
        }