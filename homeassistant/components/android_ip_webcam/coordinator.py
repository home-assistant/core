"""Coordinator object for the Android IP Webcam integration."""

from datetime import timedelta
import logging

from pydroid_ipcam import PyDroidIPCam

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AndroidIPCamDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator class for the Android IP Webcam."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        ipcam: PyDroidIPCam,
    ) -> None:
        """Initialize the Android IP Webcam."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry
        self.ipcam = ipcam
        super().__init__(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )

    async def _async_update_data(self) -> None:
        """Update Android IP Webcam entities."""
        await self.ipcam.update()
        if not self.ipcam.available:
            raise UpdateFailed
