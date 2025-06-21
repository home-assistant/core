"""Bizkaibus Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from bizkaibus.bizkaibus import BizkaibusData, BizkaibusTimetable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
type BizkaibusConfigEntry = ConfigEntry[BizkaibusUpdateCoordinator]


class BizkaibusUpdateCoordinator(DataUpdateCoordinator[BizkaibusTimetable]):
    """Bizkaibus Update Coordinator class."""

    def __init__(self, hass: HomeAssistant, api: BizkaibusData) -> None:
        """Initialize the data service."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> BizkaibusTimetable:
        """Async update wrapper."""
        timetable = await self.api.GetTimetable()
        return timetable or BizkaibusTimetable(self.api.stop)
