"""Coordinator for Rova."""

from datetime import datetime, timedelta

from rova.rova import Rova

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import get_time_zone

from .const import DOMAIN, LOGGER

EUROPE_AMSTERDAM_ZONE_INFO = get_time_zone("Europe/Amsterdam")


class RovaCoordinator(DataUpdateCoordinator[dict[str, datetime]]):
    """Class to manage fetching Rova data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, api: Rova
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=12),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, datetime]:
        """Fetch data from Rova API."""

        items = await self.hass.async_add_executor_job(self.api.get_calendar_items)

        data = {}

        for item in items:
            date = datetime.strptime(item["Date"], "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=EUROPE_AMSTERDAM_ZONE_INFO
            )
            code = item["GarbageTypeCode"].lower()
            if code not in data:
                data[code] = date

        return data
