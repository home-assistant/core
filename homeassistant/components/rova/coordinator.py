"""Coordinator for Rova."""

from datetime import datetime, timedelta
from typing import Any

from rova.rova import Rova

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import get_time_zone

from .const import DOMAIN, LOGGER


class RovaCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching Rova data."""

    def __init__(self, hass: HomeAssistant, api: Rova) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Rova API."""

        items = self.hass.async_add_executor_job(self.api.get_calendar_items)

        data = {}

        for item in items:
            date = datetime.strptime(item["Date"], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=get_time_zone("Europe/Amsterdam")
            )
            code = item["GarbageTypeCode"].lower()
            if code not in data:
                data[code] = date

        return data
