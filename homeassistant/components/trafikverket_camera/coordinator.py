"""DataUpdateCoordinator for the Trafikverket Camera integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
import logging

from pytrafikverket.trafikverket_camera import CameraInfo, TrafikverketCamera

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_LOCATION, DOMAIN

_LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = timedelta(minutes=5)


@dataclass
class CameraData:
    """Dataclass for Camera data."""

    data: CameraInfo
    image: bytes | None


class TVDataUpdateCoordinator(DataUpdateCoordinator[CameraData]):
    """A Trafikverket Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Trafikverket coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self.session = async_get_clientsession(hass)
        self._camera_api = TrafikverketCamera(self.session, entry.data[CONF_API_KEY])
        self._location = entry.data[CONF_LOCATION]

    async def _async_update_data(self) -> CameraData:
        """Fetch data from Trafikverket."""
        camera_data: CameraInfo
        image: bytes | None = None
        try:
            camera_data = await self._camera_api.async_get_camera(self._location)
        except ValueError as error:
            if "Invalid authentication" in str(error):
                raise ConfigEntryAuthFailed from error
            raise UpdateFailed from error

        if camera_data.photourl is None:
            return CameraData(data=camera_data, image=None)

        image_url = camera_data.photourl
        if camera_data.fullsizephoto:
            image_url = f"{camera_data.photourl}?type=fullsize"

        async with self.session.get(image_url, timeout=10) as get_image:
            if get_image.status not in range(200, 299):
                raise UpdateFailed("Could not retrieve image")
            image = BytesIO(await get_image.read()).getvalue()

        return CameraData(data=camera_data, image=image)
