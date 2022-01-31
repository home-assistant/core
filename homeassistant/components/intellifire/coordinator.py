"""The IntelliFire integration."""
from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientConnectionError
from async_timeout import timeout
from intellifire4py import IntellifireAsync, IntellifirePollData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator[IntellifirePollData]):
    """Class to manage the polling of the fireplace API."""

    def __init__(self, hass: HomeAssistant, api: IntellifireAsync) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self._api = api

    async def _async_update_data(self) -> IntellifirePollData:
        LOGGER.debug("Calling update loop on IntelliFire")
        async with timeout(100):
            try:
                await self._api.poll()
            except (ConnectionError, ClientConnectionError) as exception:
                raise UpdateFailed from exception
        return self._api.data

    @property
    def api(self) -> IntellifireAsync:
        """Return the API pointer."""
        return self._api

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            manufacturer="Hearth and Home",
            model="IFT-WFM",
            name="IntelliFire Fireplace",
            identifiers={("IntelliFire", f"{self.api.data.serial}]")},
            sw_version=self.api.data.fw_ver_str,
        )
