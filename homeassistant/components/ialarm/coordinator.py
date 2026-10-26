"""Coordinator for the iAlarm integration."""

import asyncio
from datetime import timedelta
import logging
from typing import override

from pyasyncialarm import IAlarm

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, IALARM_TO_HASS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

type IAlarmConfigEntry = ConfigEntry[IAlarmDataUpdateCoordinator]


class IAlarmDataUpdateCoordinator(DataUpdateCoordinator[None]):
    """Class to manage fetching iAlarm data."""

    config_entry: IAlarmConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IAlarmConfigEntry,
        ialarm: IAlarm,
        mac: str,
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

    @override
    async def _async_update_data(self) -> None:
        """Fetch data from iAlarm."""
        try:
            async with asyncio.timeout(10):
                status = await self.ialarm.get_status()
        except ConnectionError as error:
            raise UpdateFailed(error) from error
        _LOGGER.debug("iAlarm status: %s", status)

        self.state = IALARM_TO_HASS.get(status["status_value"])
