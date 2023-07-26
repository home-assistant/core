"""DataUpdateCoordinator for permobil integration."""

from dataclasses import dataclass
from datetime import timedelta
import logging

import async_timeout
from mypermobil import (
    ENDPOINT_BATTERY_INFO,
    ENDPOINT_DAILY_USAGE,
    ENDPOINT_VA_USAGE_RECORDS,
    MyPermobil,
    MyPermobilAPIException,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class MyPermobilData:
    """MyPermobil data stored in the DataUpdateCoordinator."""

    battery: dict[str, str | float | int | list | dict]
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
            update_interval=timedelta(seconds=50),
        )
        self.p_api = p_api

    async def _async_update_data(self) -> MyPermobilData:
        """Fetch data from the 3 API endpoints."""
        try:
            async with async_timeout.timeout(10):
                battery = await self.p_api.request_endpoint(ENDPOINT_BATTERY_INFO)
                daily_usage = await self.p_api.request_endpoint(ENDPOINT_DAILY_USAGE)
                records = await self.p_api.request_endpoint(ENDPOINT_VA_USAGE_RECORDS)
                return MyPermobilData(
                    battery=battery,
                    daily_usage=daily_usage,
                    records=records,
                )

        except MyPermobilAPIException as err:
            _LOGGER.error("Error fetching data from MyPermobil API: %s", err)
            raise UpdateFailed from err
