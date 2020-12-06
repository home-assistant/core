"""Support for Canary camera."""
import asyncio
from datetime import timedelta
from typing import Callable, List

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import IMAGE_JPEG, ImageFrame
import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import Throttle

from .const import (
    CONF_FFMPEG_ARGUMENTS,
    DATA_COORDINATOR,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_TIMEOUT,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import CanaryDataUpdateCoordinator

MIN_TIME_BETWEEN_SESSION_RENEW = timedelta(seconds=90)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_FFMPEG_ARGUMENTS, invalidation_version="0.118"),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(
                CONF_FFMPEG_ARGUMENTS, default=DEFAULT_FFMPEG_ARGUMENTS
            ): cv.string
        }
    ),
)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Canary sensors based on a config entry."""
    coordinator: CanaryDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    ffmpeg_arguments = entry.options.get(
        CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
    )
    cameras = []

    for location_id, location in coordinator.data["locations"].items():
        for device in location.devices:
            if device.is_online:
                cameras.append(
                    CanaryCamera(
                        hass,
                        coordinator,
                        location_id,
                        device,
                        DEFAULT_TIMEOUT,
                        ffmpeg_arguments,
                    )
                )

    async_add_entities(cameras, True)


class CanaryCamera(CoordinatorEntity, Camera):
    """An implementation of a Canary security camera."""

    def __init__(self, hass, coordinator, location_id, device, timeout, ffmpeg_args):
        """Initialize a Canary security camera."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = ffmpeg_args
        self._location_id = location_id
        self._device = device
        self._device_id = device.device_id
        self._device_name = device.name
        self._device_type_name = device.device_type["name"]
        self._timeout = timeout
        self._live_stream_session = None

    @property
    def location(self):
        """Return information about the location."""
        return self.coordinator.data["locations"][self._location_id]

    @property
    def name(self):
        """Return the name of this device."""
        return self._device_name

    @property
    def unique_id(self):
        """Return the unique ID of this camera."""
        return str(self._device_id)

    @property
    def device_info(self):
        """Return the device_info of the device."""
        return {
            "identifiers": {(DOMAIN, str(self._device_id))},
            "name": self._device_name,
            "model": self._device_type_name,
            "manufacturer": MANUFACTURER,
        }

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self.location.is_recording

    @property
    def motion_detection_enabled(self):
        """Return the camera motion detection status."""
        return not self.location.is_recording

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        await self.hass.async_add_executor_job(self.renew_live_stream_session)

        ffmpeg = ImageFrame(self._ffmpeg.binary)
        image = await asyncio.shield(
            ffmpeg.get_image(
                self._live_stream_session.live_stream_url,
                output_format=IMAGE_JPEG,
                extra_cmd=self._ffmpeg_arguments,
            )
        )
        return image

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if self._live_stream_session is None:
            return

        stream = CameraMjpeg(self._ffmpeg.binary)
        await stream.open_camera(
            self._live_stream_session.live_stream_url, extra_cmd=self._ffmpeg_arguments
        )

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await stream.close()

    @Throttle(MIN_TIME_BETWEEN_SESSION_RENEW)
    def renew_live_stream_session(self):
        """Renew live stream session."""
        self._live_stream_session = self.coordinator.canary.get_live_stream_session(
            self._device
        )
