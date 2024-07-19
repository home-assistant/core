"""Update coordinator for Pinecil Integration."""

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


class PinecilCoordinator(DataUpdateCoordinator[LiveDataResponse]):
    """Pinecil coordinator."""

    device: DeviceInfoResponse
    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, pinecil: Pynecil) -> None:
        """Initialize Pinecil coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.pinecil = pinecil

    async def _async_update_data(self) -> LiveDataResponse:
        """Fetch data from Pinecil."""

        try:
            self.device = await self.pinecil.get_device_info()
            return await self.pinecil.get_live_data()

        except CommunicationError as e:
            raise UpdateFailed("Cannot connect to device") from e
