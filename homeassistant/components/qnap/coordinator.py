"""Data coordinator for the qnap integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from qnapstats import QNAPStats

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
UPDATE_INTERVAL = timedelta(minutes=1)

_LOGGER = logging.getLogger(__name__)


class QnapCoordinator(DataUpdateCoordinator[None]):
    """Custom coordinator for the qnap integration."""

    def __init__(self, hass: HomeAssistant, api: QNAPStats) -> None:
        """Initialize the qnap coordinator."""
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL
        )

        self.api = api

    async def _async_update_data(self) -> None:
        """Get the latest data from the Qnap API."""
        datas = {}
        datas["system_stats"] = await self.hass.async_add_executor_job(self.api.get_system_stats)
        datas["system_health"] = await self.hass.async_add_executor_job(
            self.api.get_system_health
        )
        datas["smart_drive_health"] = await self.hass.async_add_executor_job(
            self.api.get_smart_disk_health
        )
        datas["volumes"] = await self.hass.async_add_executor_job(self.api.get_volumes)
        datas["bandwidth"] = await self.hass.async_add_executor_job(self.api.get_bandwidth)
        return datas
