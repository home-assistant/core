"""Coordinator for PJLink."""
from __future__ import annotations

import asyncio
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import _LOGGER, UPDATE_INTERVAL
from .device import PJLinkDevice


class PJLinkUpdateCoordinator(DataUpdateCoordinator):
    """DataUpdateCoordinator to gather data for a specific PJLink device."""

    _device_label: str

    _first_metadata_run: bool = False

    def __init__(self, hass: HomeAssistant, device: PJLinkDevice) -> None:
        """Initialize the DataUpdateCoordinator."""
        self.lock = asyncio.Lock()
        self.device = device

        self._device_label = f"{device.host}_{device.port}"

        update_interval = timedelta(seconds=UPDATE_INTERVAL)

        super().__init__(
            hass, _LOGGER, name=self.device_label, update_interval=update_interval
        )

    async def _async_update_data(self) -> None:
        """Fetch all data from the PJLink device."""

        async with self.lock:
            await self.device.async_update()

    @property
    def device_name(self) -> str:
        """Get the projector name."""
        return self.device.name

    @property
    def manufacturer(self) -> str | None:
        """Get the projector manufacturer."""
        return self.device.manufacturer

    @property
    def model(self) -> str | None:
        """Get the projector model."""
        return self.device.model

    @property
    def device_label(self) -> str:
        """Get the device label."""
        return self._device_label
