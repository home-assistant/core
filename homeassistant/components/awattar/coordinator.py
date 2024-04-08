"""The Coordinator for aWATTar."""

from __future__ import annotations

from datetime import timedelta
from typing import NamedTuple

from awattar import AsyncAwattarClient, AwattarConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(hours=1)


class AwattarData(NamedTuple):
    """Class for defining data in dict."""

    awattar: AsyncAwattarClient


class AwattarDataUpdateCoordinator(DataUpdateCoordinator[AwattarData]):
    """Class to manage fetching aWATTar data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize global aWATTar data updater."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

        self.awattar = AsyncAwattarClient(
            session=async_get_clientsession(hass),
            country=self.config_entry.data[CONF_COUNTRY_CODE],
        )

    async def _async_update_data(self) -> AwattarData:
        """Fetch data from aWATTar."""

        try:
            now = dt_util.now()
            start = now.replace(minute=0, second=0, microsecond=0)
            LOGGER.debug(f"Updating from {start} ...")
            await self.awattar.request(
                start_time=start, end_time=start + timedelta(days=2)
            )

        except AwattarConnectionError as err:
            raise UpdateFailed("Error communicating with aWATTar API") from err

        return AwattarData(awattar=self.awattar)
