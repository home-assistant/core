"""Define support for Eufy Security cameras/doorbells."""
import asyncio
import logging

from eufy_security.errors import EufySecurityError
from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import ImageFrame, IMAGE_JPEG

from homeassistant.components.camera import SUPPORT_ON_OFF, SUPPORT_STREAM, Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream

from .const import DATA_API, DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_HARDWARE_VERSION = "hardware_version"
ATTR_SERIAL = "serial_number"
ATTR_SOFTWARE_VERSION = "software_version"

DEFAULT_ATTRIBUTION = "Data provided by Eufy Security"
DEFAULT_FFMPEG_ARGUMENTS = "-pred 1"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Eufy Security sensors based on a config entry."""
    api = hass.data[DOMAIN][DATA_API][entry.entry_id]
    async_add_entities(
        [EufySecurityCam(hass, camera) for camera in api.cameras.values()], True
    )


class EufySecurityCam(Camera):
    """Define a Eufy Security camera/doorbell."""

    def __init__(self, hass, camera):
        """Initialize."""
        super().__init__()

        self._async_unsub_dispatcher_connect = None
        self._camera = camera
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = DEFAULT_FFMPEG_ARGUMENTS
        self._ffmpeg_image_frame = ImageFrame(self._ffmpeg.binary, loop=hass.loop)
        self._ffmpeg_stream = CameraMjpeg(self._ffmpeg.binary, loop=hass.loop)
        self._last_image = None
        self._last_image_url = None
        self._stream_url = None

    @property
    def brand(self):
        """Return the camera brand."""
        return "Eufy Security"

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_HARDWARE_VERSION: self._camera.hardware_version,
            ATTR_SERIAL: self._camera.serial,
            ATTR_SOFTWARE_VERSION: self._camera.software_version,
        }

    @property
    def model(self):
        """Return the name of this camera."""
        return self._camera.model

    @property
    def name(self):
        """Return the name of this camera."""
        return self._camera.name

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_ON_OFF | SUPPORT_STREAM

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._camera.serial

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        if self._last_image_url != self._camera.last_camera_image_url:
            self._last_image = await asyncio.shield(
                self._ffmpeg_image_frame.get_image(
                    self._camera.last_camera_image_url,
                    output_format=IMAGE_JPEG,
                    extra_cmd=self._ffmpeg_arguments,
                )
            )
            self._last_image_url = self._camera.last_camera_image_url

        return self._last_image

    async def async_turn_off(self):
        """Turn off the RTSP stream."""
        try:
            await self._camera.async_stop_stream()
            _LOGGER.info("Stream stopped for %s", self._camera.name)
        except EufySecurityError as err:
            _LOGGER.error("Unable to stop stream (%s): %s", self._camera.name, err)

        self._stream_url = None

    async def async_turn_on(self):
        """Turn on the RTSP stream."""
        try:
            self._stream_url = await self._camera.async_start_stream()
            _LOGGER.info("Stream started (%s): %s", self._camera.name, self._stream_url)
        except EufySecurityError as err:
            _LOGGER.error("Unable to start stream (%s): %s", self._camera.name, err)

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if not self._stream_url:
            return await self.async_camera_image()

        await self._ffmpeg_stream.open_camera(
            self._stream_url, extra_cmd=self._ffmpeg_arguments
        )

        try:
            stream_reader = await self._ffmpeg_stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass,
                request,
                stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type,
            )
        finally:
            await self._ffmpeg_stream.close()
