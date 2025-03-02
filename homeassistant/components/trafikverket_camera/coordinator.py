"""DataUpdateCoordinator for the Trafikverket Camera integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from io import BytesIO
import logging
from typing import TYPE_CHECKING

import aiohttp
from pytrafikverket import (
    CameraInfoModel,
    InvalidAuthentication,
    MultipleCamerasFound,
    NoCameraFound,
    TrafikverketCamera,
    UnknownError,
)

from homeassistant.const import CONF_API_KEY, CONF_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import TVCameraConfigEntry

_LOGGER = logging.getLogger(__name__)
TIME_BETWEEN_UPDATES = timedelta(minutes=5)


@dataclass
class CameraData:
    """Dataclass for Camera data."""

    data: CameraInfoModel
    image: bytes | None


class TVDataUpdateCoordinator(DataUpdateCoordinator[CameraData]):
    """A Trafikverket Data Update Coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: TVCameraConfigEntry) -> None:
        """Initialize the Trafikverket coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=TIME_BETWEEN_UPDATES,
        )
        self.session = async_get_clientsession(hass)
        self._camera_api = TrafikverketCamera(
            self.session, config_entry.data[CONF_API_KEY]
        )
        self._id = config_entry.data[CONF_ID]

    async def _async_update_data(self) -> CameraData:
        """Fetch data from Trafikverket."""
        camera_data: CameraInfoModel
        image: bytes | None = None
        try:
            camera_data = await self._camera_api.async_get_camera(self._id)
        except (NoCameraFound, MultipleCamerasFound, UnknownError) as error:
            raise UpdateFailed from error
        except InvalidAuthentication as error:
            raise ConfigEntryAuthFailed from error

        if camera_data.photourl is None:
            return CameraData(data=camera_data, image=None)

        image_url = camera_data.photourl
        if camera_data.fullsizephoto:
            image_url = f"{camera_data.photourl}?type=fullsize"

        async with self.session.get(
            image_url, timeout=aiohttp.ClientTimeout(total=10)
        ) as get_image:
            if get_image.status not in range(200, 299):
                raise UpdateFailed("Could not retrieve image")
            image = BytesIO(await get_image.read()).getvalue()

        return CameraData(data=camera_data, image=image)
