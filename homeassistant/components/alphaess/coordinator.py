"""Coordinator for AlphaEss integration."""
import datetime
import json
import logging

import aiohttp
from alphaess import alphaess

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER: logging.Logger = logging.getLogger(__package__)


class AlphaESSDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: alphaess.alphaess) -> None:
        """Initialize."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = client
        self.update_method = self._async_update_data
        self.data: dict[str, dict[str, float]] = {}

    async def _async_update_data(self):
        """Update data via library."""
        try:
            _LOGGER.info("Trying to query AlphaESS api data")
            jsondata: json = await self.api.getdata()
            for invertor in jsondata:
                index = int(datetime.date.today().strftime("%d")) - 1
                inverterdata: dict[str, any] = {}
                inverterdata.update({"Model": invertor["minv"]})
                inverterdata.update(
                    {"Solar Production": invertor["statistics"]["EpvT"]}
                )
                inverterdata.update(
                    {"Solar to Battery": invertor["statistics"]["Epvcharge"]}
                )
                inverterdata.update({"Solar to Grid": invertor["statistics"]["Eout"]})
                inverterdata.update(
                    {"Solar to Load": invertor["statistics"]["Epv2load"]}
                )
                inverterdata.update({"Total Load": invertor["statistics"]["EHomeLoad"]})
                inverterdata.update(
                    {"Grid to Load": invertor["statistics"]["EGrid2Load"]}
                )
                inverterdata.update(
                    {"Grid to Battery": invertor["statistics"]["EGridCharge"]}
                )
                inverterdata.update({"State of Charge": invertor["statistics"]["Soc"]})
                inverterdata.update(
                    {"Charge": invertor["system_statistics"]["ECharge"][index]}
                )
                inverterdata.update(
                    {"Discharge": invertor["system_statistics"]["EDischarge"][index]}
                )
            self.data.update({invertor["sys_sn"]: inverterdata})
            return self.data
        except (
            aiohttp.client_exceptions.ClientConnectorError,
            aiohttp.ClientResponseError,
        ) as error:
            raise UpdateFailed(error) from error
