"""The CCL Data Update Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
import time

from aioccl import CCLDevice, CCLSensor

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type CCLConfigEntry = ConfigEntry[CCLDevice]


class CCLCoordinator(DataUpdateCoordinator[dict[str, CCLSensor]]):
    """Class to manage processing CCL data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: CCLDevice,
        entry: CCLConfigEntry,
    ) -> None:
        """Initialize global CCL data updater."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=600),
            update_method=self._async_update_data,
            always_update=True,
        )

        self.device = device

    async def _async_update_data(self) -> dict[str, CCLSensor]:
        _LOGGER.debug("Polling at %s", time.monotonic())
        if self.device.last_update_time is None:
            raise UpdateFailed("Device is offline or not ready")
        if time.monotonic() - self.device.last_update_time >= 600:
            raise UpdateFailed("Device is offline or not ready")
        return self.device.get_sensors  # raise CCLDataUpdateException when failed
