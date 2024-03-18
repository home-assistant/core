"""Swidget Device Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from swidget import SwidgetDevice, SwidgetException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
REQUEST_REFRESH_DELAY = 0.35


class SwidgetDataUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific Swidget device."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: SwidgetDevice,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific device."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            name=device.ip_address,
            update_interval=timedelta(seconds=30.0),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=False
            ),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch all device and sensor data from api."""
        # No need to call any explicit update function here. The device will update the state itself
        try:
            await self.device.get_state()
        except SwidgetException as ex:
            raise UpdateFailed(ex) from ex
        return {}
