"""Swidget Device Coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from swidget import SwidgetDevice, SwidgetException

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
REQUEST_REFRESH_DELAY = 1.0


class SwidgetDataUpdateCoordinator(DataUpdateCoordinator[None]):
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
            always_update=False,
            update_interval=timedelta(seconds=300),
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=0.35, immediate=False
            ),
        )

    async def async_initialize(self) -> Any:
        """Initialize a callback for any websocket events received from the device."""
        return self.device.add_event_callback(self.websocket_event_callback)

    @callback
    async def websocket_event_callback(self, message: dict[Any, Any]) -> None:
        """Update the entity state."""
        self.async_set_updated_data(data=None)

    async def _async_update_data(self) -> None:
        """Fetch all device and sensor data from api."""
        try:
            await self.device.get_state()
        except SwidgetException as ex:
            raise UpdateFailed(ex) from ex
