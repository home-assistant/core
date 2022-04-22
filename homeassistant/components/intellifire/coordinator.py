"""The IntelliFire integration."""
from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientConnectionError
from async_timeout import timeout
from intellifire4py import (
    IntellifireAsync,
    IntellifireControlAsync,
    IntellifirePollData,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class IntellifireDataUpdateCoordinator(DataUpdateCoordinator[IntellifirePollData]):
    """Class to manage the polling of the fireplace API."""

    def __init__(
        self,
        hass: HomeAssistant,
        read_api: IntellifireAsync,
        control_api: IntellifireControlAsync,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self._read_api = read_api
        self._control_api = control_api

    async def _async_update_data(self) -> IntellifirePollData:
        LOGGER.debug("Calling update loop on IntelliFire")
        async with timeout(100):
            try:
                await self._read_api.poll()
            except (ConnectionError, ClientConnectionError) as exception:
                raise UpdateFailed from exception
        return self._read_api.data

    @property
    def read_api(self) -> IntellifireAsync:
        """Return the Status API pointer."""
        return self._read_api

    @property
    def control_api(self) -> IntellifireControlAsync:
        """Return the control API."""
        return self._control_api

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            manufacturer="Hearth and Home",
            model="IFT-WFM",
            name="IntelliFire Fireplace",
            identifiers={("IntelliFire", f"{self.read_api.data.serial}]")},
            sw_version=self.read_api.data.fw_ver_str,
            configuration_url=f"http://{self.read_api.ip}/poll",
        )
