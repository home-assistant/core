"""Representation of VeSync data coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from pyvesync import VeSync

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class VeSyncDataCoordinator(DataUpdateCoordinator):
    """Class representing data coordinator for VeSync devices."""

    def __init__(self, hass: HomeAssistant, manager: VeSync) -> None:
        """Initialize."""
        self._manager = manager

        super().__init__(
            hass,
            _LOGGER,
            name="VeSyncDataCoordinator",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""

        try:
            return await self.hass.async_add_executor_job(self._manager.update)
        except Exception as error:
            raise UpdateFailed(error) from error
