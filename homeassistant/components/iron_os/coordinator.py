"""Update coordinator for IronOS Integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from pynecil import CommunicationError, DeviceInfoResponse, LiveDataResponse, Pynecil

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


class IronOSCoordinator(DataUpdateCoordinator[LiveDataResponse]):
    """IronOS coordinator."""

    device_info: DeviceInfoResponse
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, device: Pynecil) -> None:
        """Initialize IronOS coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device

    async def _async_update_data(self) -> LiveDataResponse:
        """Fetch data from Device."""

        try:
            return await self.device.get_live_data()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e

    async def _async_setup(self) -> None:
        """Set up the coordinator."""

        try:
            self.device_info = await self.device.get_device_info()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e
