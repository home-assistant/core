"""DataUpdateCoordinator for permobil integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging

from mypermobil import MyPermobil, MyPermobilAPIException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


@dataclass
class MyPermobilData:
    """MyPermobil data stored in the DataUpdateCoordinator."""

    battery: dict[str, str | float | int | bool | list | dict]
    daily_usage: dict[str, str | float | int | list | dict]
    records: dict[str, str | float | int | list | dict]


class MyPermobilCoordinator(DataUpdateCoordinator[MyPermobilData]):
    """MyPermobil coordinator."""

    def __init__(self, hass: HomeAssistant, p_api: MyPermobil) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="permobil",
            update_interval=timedelta(minutes=5),
        )
        self.p_api = p_api

    async def _async_update_data(self) -> MyPermobilData:
        """Fetch data from the 3 API endpoints."""
        try:
            async with asyncio.timeout(10):
                battery = await self.p_api.get_battery_info()
                daily_usage = await self.p_api.get_daily_usage()
                records = await self.p_api.get_usage_records()
                return MyPermobilData(
                    battery=battery,
                    daily_usage=daily_usage,
                    records=records,
                )

        except MyPermobilAPIException as err:
            _LOGGER.exception(
                "Error fetching data from MyPermobil API for account %s",
                self.p_api.email,
            )
            raise UpdateFailed from err
