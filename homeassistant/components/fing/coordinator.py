"""DataUpdateCoordinator for Fing integration."""

from datetime import timedelta
import logging
from random import randrange
from typing import Self

from fing_agent_api import FingAgent
from fing_agent_api.models import Device

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AGENT_IP, AGENT_KEY, AGENT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FingDataFetcher:
    """Keep data from the Fing Agent."""

    def __init__(self, hass: HomeAssistant, ip: str, port: int, key: str) -> None:
        """Initialize Fing entity data."""
        self._hass = hass
        self._fing = FingAgent(ip, port, key)
        self._network_id = None
        self._devices: dict[str, Device] = {}

    def get_devices(self):
        """Return all the devices."""
        return self._devices

    def get_network_id(self) -> str | None:
        """Return the network id."""
        return self._network_id

    async def fetch_data(self) -> Self:
        """Fecth data from Fing."""
        response = await self._fing.get_devices()
        self._network_id = response.network_id
        self._devices = {device.mac: device for device in response.devices}
        return self


class FingDataUpdateCoordinator(DataUpdateCoordinator[FingDataFetcher]):
    """Class to manage fetching data from Fing Agent."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global Fing updater."""
        self._fing_fetcher = FingDataFetcher(
            hass,
            config_entry.data[AGENT_IP],
            int(config_entry.data.get(AGENT_PORT, "49090")),
            config_entry.data[AGENT_KEY],
        )

        update_interval = timedelta(seconds=randrange(25, 35))
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> FingDataFetcher:
        """Fetch data from Fing Agent."""
        try:
            return await self._fing_fetcher.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
