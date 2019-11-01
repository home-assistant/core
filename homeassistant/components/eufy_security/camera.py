"""Define support for Eufy Security cameras/doorbells."""
import asyncio
import logging

from haffmpeg.camera import CameraMjpeg
from haffmpeg.tools import ImageFrame, IMAGE_JPEG

from homeassistant.components.camera import Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_aiohttp_proxy_stream
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_API, DOMAIN, TOPIC_DATA_UPDATE

_LOGGER = logging.getLogger(__name__)

ATTR_HARDWARE_VERSION = "hardware_version"
ATTR_MODEL = "model"
ATTR_SERIAL = "serial_number"
ATTR_SOFTWARE_VERSION = "software_version"

DEFAULT_ATTRIBUTION = "Data provided by Eufy Security"


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
        self._stream_url = None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: DEFAULT_ATTRIBUTION,
            ATTR_HARDWARE_VERSION: self._camera.hardware_version,
            ATTR_MODEL: self._camera.model,
            ATTR_SERIAL: self._camera.serial,
            ATTR_SOFTWARE_VERSION: self._camera.software_version,
        }

    @property
    def name(self):
        """Return the name of this camera."""
        return self._camera.name

    @property
    def should_poll(self):
        """Return False, updates are controlled via the hub."""
        return False

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._camera.serial

    async def async_added_to_hass(self):
        """Register callbacks."""

        @callback
        def update():
            """Update the camera."""
            self.hass.async_create_task(self._camera.async_update())
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_DATA_UPDATE, update
        )

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        ffmpeg = ImageFrame(self._ffmpeg.binary, loop=self.hass.loop)

        image = await asyncio.shield(
            ffmpeg.get_image(
                self._camera.last_camera_image_url, output_format=IMAGE_JPEG
            )
        )
        return image

    async def async_turn_off(self):
        """Turn off the RTSP stream."""
        if not self._stream_url:
            return

        _LOGGER.debug("Stopping stream: %s", self._stream_url)
        await self._camera.async_stop_stream()
        self._stream_url = None

    async def async_turn_on(self):
        """Turn on the RTSP stream."""
        if self._stream_url:
            return

        self._stream_url = await self._camera.async_start_stream()
        _LOGGER.debug("Starting stream: %s", self._stream_url)

    async def async_will_remove_from_hass(self):
        """Disconnect dispatcher listener when removed."""
        if self._async_unsub_dispatcher_connect:
            self._async_unsub_dispatcher_connect()

    async def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        if not self._stream_url:
            _LOGGER.warning(
                'Turn the "%s" camera on before attempting to view the stream',
                self.name,
            )
            return

        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(self._stream_url)

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
