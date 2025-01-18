"""Bizkaibus Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from bizkaibus.bizkaibus import BizkaibusData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)
type BizkaibusConfigEntry = ConfigEntry[BizkaibusUpdateCoordinator]


class BizkaibusUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """BizkaibusUpdateCoordinator - In charge of downloading the data for a site."""

    def __init__(self, hass: HomeAssistant, api: Bizkaibus) -> None:
        """Initialize the data service."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Async update wrapper."""
        return await self.api.update()


class Bizkaibus:
    """The class for handling the data retrieval."""

    def __init__(self, stop) -> None:
        """Initialize the data object."""
        self.bridge = BizkaibusData(stop)
        self.info = None

    async def update(self) -> dict[str, Any]:
        """Retrieve the information from API."""
        return await self.bridge.GetTimetable()
