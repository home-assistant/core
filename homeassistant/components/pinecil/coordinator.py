"""Update coordinator for Pinecil Integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from bleak.exc import BleakError
from pinecil import DeviceDisconnectedException, DeviceNotFoundException, Pinecil

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import Throttle

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


class PinecilCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Pinecil coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        pinecil: Pinecil,
    ) -> None:
        """Initialize Pinecil coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pinecil = pinecil
        self.hass = hass
        self.device: dict[str, str] = {}
        self.settings: dict[str, int] = {}

    async def _async_update_data(self) -> dict[str, int]:
        """Fetch data from Pinecil."""

        try:
            if not self.device:
                self.device = await self.pinecil.get_info()

            await self.get_settings()

            return await self.pinecil.get_live_data()

        except (
            DeviceDisconnectedException,
            DeviceNotFoundException,
            BleakError,
        ) as e:
            raise UpdateFailed(
                f"Cannot connect to {self.device.get("name", "Pinecil")}"
            ) from e

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def get_settings(self) -> None:
        """Fetch settings from Pinecil."""

        # pretty ugly, but the get_all_settings method times out
        # because it slows down polling of characteristics with sleep

        for setting in self.pinecil.crx_settings:
            key, value = await self.pinecil._Pinecil__read_setting(setting)  # noqa: SLF001
            self.settings[key] = value
