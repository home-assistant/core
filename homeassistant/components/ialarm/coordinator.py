"""Coordinator for the iAlarm integration."""

from __future__ import annotations

import asyncio
import logging

from pyialarm import IAlarm

from homeassistant.components.alarm_control_panel import (
    SCAN_INTERVAL,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, IALARM_TO_HASS

_LOGGER = logging.getLogger(__name__)


class IAlarmDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching iAlarm data."""

    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, ialarm: IAlarm, mac: str
    ) -> None:
        """Initialize global iAlarm data updater."""
        self.ialarm = ialarm
        self.state: AlarmControlPanelState | None = None
        self.host: str = ialarm.host
        self.mac = mac

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    def _update_data(self) -> None:
        """Fetch data from iAlarm via sync functions."""
        status = self.ialarm.get_status()
        _LOGGER.debug("iAlarm status: %s", status)

        self.state = IALARM_TO_HASS.get(status)

    async def _async_update_data(self) -> None:
        """Fetch data from iAlarm."""
        try:
            async with asyncio.timeout(10):
                await self.hass.async_add_executor_job(self._update_data)
        except ConnectionError as error:
            raise UpdateFailed(error) from error
