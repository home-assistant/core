"""Data coordinator for the ezbeq Profile Loader integration."""

from datetime import timedelta
import logging

from httpx import HTTPStatusError, RequestError
from pyezbeq.errors import DeviceInfoEmpty
from pyezbeq.ezbeq import EzbeqClient
from pyezbeq.models import BeqDevice

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class EzbeqCoordinator(DataUpdateCoordinator):
    """Coordinator for fetching ezbeq data."""

    def __init__(self, hass: HomeAssistant, client: EzbeqClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ezbeq",
            update_interval=timedelta(seconds=30),
        )
        self.client = client
        self.current_profile = ""
        self.current_media_type = ""
        self.version = ""
        self.devices: list[BeqDevice] = []

    async def _async_update_data(self):
        """Fetch data from the ezbeq API."""
        try:
            await self.client.get_status()
            await self.client.get_version()
        except (DeviceInfoEmpty, HTTPStatusError, RequestError) as err:
            _LOGGER.error("Error fetching ezbeq data: %s", err)
            raise
        self.devices = self.client.device_info
        self.current_profile = self.client.current_profile
        self.current_media_type = self.client.current_media_type
        self.version = self.client.version
        return {
            "devices": self.devices,
            "current_profile": self.current_profile,
            "current_media_type": self.current_media_type,
            "version": self.version,
        }
