"""Home Assistant hardware firmware update coordinator."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiohttp import ClientSession
from ha_silabs_firmware_client import (
    FirmwareManifest,
    FirmwareUpdateClient,
    ManifestMissing,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


FIRMWARE_REFRESH_INTERVAL = timedelta(hours=8)


class FirmwareUpdateCoordinator(DataUpdateCoordinator[FirmwareManifest]):
    """Coordinator to manage firmware updates."""

    def __init__(self, hass: HomeAssistant, session: ClientSession, url: str) -> None:
        """Initialize the firmware update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="firmware update coordinator",
            update_interval=FIRMWARE_REFRESH_INTERVAL,
        )
        self.hass = hass
        self.session = session

        self.client = FirmwareUpdateClient(url, session)

    async def _async_update_data(self) -> FirmwareManifest:
        try:
            return await self.client.async_update_data()
        except ManifestMissing as err:
            raise UpdateFailed(
                "GitHub release assets haven't been uploaded yet"
            ) from err
