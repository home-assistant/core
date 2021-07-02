"""Provides the switchbot DataUpdateCoordinator."""
from __future__ import annotations

from asyncio import Lock
from datetime import timedelta
import logging

import switchbot  # pylint: disable=import-error

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
CONNECT_LOCK = Lock()


class SwitchbotDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching switchbot data."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        update_interval: int,
        api: switchbot,
        retry_count: int,
        scan_timeout: int,
    ) -> None:
        """Initialize global switchbot data updater."""
        self.switchbot_api = api
        self.retry_count = retry_count
        self.scan_timeout = scan_timeout
        self._switchbot_data = {}
        self.update_interval = timedelta(seconds=update_interval)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=self.update_interval
        )

    def _update_data(self) -> bool:
        """Fetch device states from switchbot api."""

        self._switchbot_data = self.switchbot_api.GetSwitchbotDevices().discover(
            retry=self.retry_count, scan_timeout=self.scan_timeout
        )

        if self._switchbot_data:
            return True
        return False

    async def _async_update_data(self) -> dict | None:
        """Fetch data from switchbot."""

        async with CONNECT_LOCK:
            _update_success = await self.hass.async_add_executor_job(self._update_data)

        if not _update_success:
            raise UpdateFailed("Unable to fetch switchbot services data")

        return self._switchbot_data
