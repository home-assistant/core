"""Coordinator for the Lektrico Charging Station integration."""

from __future__ import annotations

from datetime import timedelta

from aiohttp import ClientSession
from lektricowifi import DeviceConnectionError, lektricowifi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

SCAN_INTERVAL = timedelta(seconds=10)


class LektricoDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """The device class for Lektrico device."""

    def __init__(
        self,
        hass: HomeAssistant,
        friendly_name: str,
        host: str,
        session: ClientSession,
    ) -> None:
        """Initialize a Lektrico Device."""
        self.device = lektricowifi.Device(
            host,
            session=session,
        )
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}-{friendly_name}",
            update_interval=SCAN_INTERVAL,
        )
        self.serial_number: int
        self.board_revision: str
        self.device_type: str

    async def get_config(self) -> None:
        """Get device's config. This is only asked once."""
        settings = await self.device.device_config()
        self.serial_number = settings.serial_number
        self.board_revision = settings.board_revision
        self.device_type = settings.type

    async def _async_update_data(self) -> lektricowifi.Info:
        """Async Update device state."""
        try:
            info = await self.device.device_info(self.device_type)
            return info
        except DeviceConnectionError as lek_ex:
            raise UpdateFailed(lek_ex) from lek_ex
