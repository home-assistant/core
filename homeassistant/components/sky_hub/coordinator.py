"""DataUpdateCoordinator for the Sky Hub integration."""

from datetime import timedelta
import logging
from typing import override

import aiohttp
from pyskyqhub.skyq_hub import SkyQHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(seconds=30)

type SkyHubConfigEntry = ConfigEntry[SkyHubDataUpdateCoordinator]


class SkyHubDataUpdateCoordinator(DataUpdateCoordinator[dict[str, str]]):
    """Class to manage fetching data from the Sky Hub."""

    config_entry: SkyHubConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: SkyHubConfigEntry) -> None:
        """Initialize the coordinator using the config entry."""
        self.host = config_entry.data[CONF_HOST]
        self.hub = SkyQHub(async_get_clientsession(hass), self.host)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN} - {self.host}",
            update_interval=UPDATE_INTERVAL,
        )

    @override
    async def _async_update_data(self) -> dict[str, str]:
        """Fetch the connected devices from the Sky Hub, keyed by MAC address."""
        try:
            data = await self.hub.async_get_skyhub_data()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(
                f"Failed to fetch data from Sky Hub {self.host}"
            ) from err
        if data is None:
            raise UpdateFailed(f"Failed to fetch data from Sky Hub {self.host}")
        return {device.mac: device.name for device in data}
