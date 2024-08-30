"""DataUpdateCoordinator for Fing integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Self

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AGENT_IP, AGENT_SECRET, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FingDataFetcher:
    """Keep data from the Fing Agent."""

    # def __init__(self, hass: HomeAssistant, config: MappingProxyType[str, Any]) -> None:
    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Initialize Fing entity data."""
        self._hass = hass
        self._config = config.data

        # temporary solution, should be None and retrieved from the fing unit
        # if the retrieve fails should be throw an error
        # also the commented out init is the one to use
        self._network_id = config.entry_id

        self._devices: dict[str, str] = {}

    def get_devices(self):
        """Return all the devices."""
        return self._devices

    def get_network_id(self) -> str | None:
        """Return the network id."""
        return self._network_id

    async def fetch_data(self) -> Self:
        """Fecth data from Fing."""

        # move fetch inside a library
        ip = self._config[AGENT_IP]
        secret = self._config[AGENT_SECRET]
        url = f"http://{ip}:49090/1/devices?auth={secret}"
        response = await asyncio.to_thread(requests.get, url)
        for device in response.json()["devices"]:
            if "mac" in device:
                self._devices[device["mac"]] = device
        self._network_id = response.json().get("networkId", None)

        # END
        return self


class FingDataUpdateCoordinator(DataUpdateCoordinator[FingDataFetcher]):
    """Class to manage fetching data from Fing Agent."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize global Fing updater."""
        self._fing_fetcher = FingDataFetcher(hass, config_entry)

        # update_interval = timedelta(minutes=randrange(55, 65))
        update_interval = timedelta(seconds=5)
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> FingDataFetcher:
        """Fetch data from Fing Agent."""
        try:
            return await self._fing_fetcher.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err
