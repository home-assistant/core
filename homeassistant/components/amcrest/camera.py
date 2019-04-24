"""Support for Amcrest IP cameras."""
import asyncio
import logging

from homeassistant.components.camera import (
    Camera, SUPPORT_ON_OFF, SUPPORT_STREAM)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream, async_aiohttp_proxy_web,
    async_get_clientsession)

from . import DATA_AMCREST, STREAM_SOURCE_LIST, TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    device_name = discovery_info[CONF_NAME]
    amcrest = hass.data[DATA_AMCREST][device_name]

    async_add_entities([AmcrestCam(hass, amcrest)], True)


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, hass, amcrest):
        """Initialize an Amcrest camera."""
        super(AmcrestCam, self).__init__()
        self._name = amcrest.name
        self._camera = amcrest.device
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = amcrest.ffmpeg_arguments
        self._stream_source = amcrest.stream_source
        self._resolution = amcrest.resolution
        self._token = self._auth = amcrest.authentication
        self._is_recording = False
        self._model = None
        self._snapshot_lock = asyncio.Lock()

    async def async_camera_image(self):
        """Return a still image response from the camera."""
        from amcrest import AmcrestError

        if not self.is_on:
            _LOGGER.error(
                'Attempt to take snaphot when %s camera is off', self.name)
            return None
        async with self._snapshot_lock:
            try:
                # Send the request to snap a picture and return raw jpg data
                response = await self.hass.async_add_executor_job(
                    self._camera.snapshot, self._resolution)
                return response.data
            except AmcrestError as error:
                _LOGGER.error(
                    'Could not get image from %s camera due to error: %s',
                    self.name, error)
                return None

    async def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        # The snapshot implementation is handled by the parent class
        if self._stream_source == STREAM_SOURCE_LIST['snapshot']:
            return await super().handle_async_mjpeg_stream(request)

        if self._stream_source == STREAM_SOURCE_LIST['mjpeg']:
            # stream an MJPEG image stream directly from the camera
            websession = async_get_clientsession(self.hass)
            streaming_url = self._camera.mjpeg_url(typeno=self._resolution)
            stream_coro = websession.get(
                streaming_url, auth=self._token, timeout=TIMEOUT)

            return await async_aiohttp_proxy_web(
                self.hass, request, stream_coro)

        # streaming via ffmpeg
        from haffmpeg.camera import CameraMjpeg

        streaming_url = self._camera.rtsp_url(typeno=self._resolution)
        stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
        await stream.open_camera(
            streaming_url, extra_cmd=self._ffmpeg_arguments)

        try:
            stream_reader = await stream.get_reader()
            return await async_aiohttp_proxy_stream(
                self.hass, request, stream_reader,
                self._ffmpeg.ffmpeg_stream_content_type)
        finally:
            await stream.close()

    # Entity property overrides

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name

    @property
    def supported_features(self):
        """Return supported features."""
        return SUPPORT_ON_OFF | SUPPORT_STREAM

    # Camera property overrides

    @property
    def is_recording(self):
        """Return true if the device is recording."""
        return self._is_recording

    @property
    def brand(self):
        """Return the camera brand."""
        return 'Amcrest'

    @property
    def model(self):
        """Return the camera model."""
        return self._model

    @property
    def stream_source(self):
        """Return the source of the stream."""
        return self._camera.rtsp_url(typeno=self._resolution)

    @property
    def is_on(self):
        """Return true if on."""
        return self.is_streaming

    # Other Entity method overrides

    def update(self):
        """Update entity status."""
        from amcrest import AmcrestError

        _LOGGER.debug('Pulling data from %s camera', self.name)
        if self._model is None:
            try:
                self._model = self._camera.device_type.split('=')[-1].strip()
            except AmcrestError as error:
                _LOGGER.error(
                    'Could not get %s camera model due to error: %s',
                    self.name, error)
                self._model = ''
        try:
            self.is_streaming = self._camera.video_enabled
            self._is_recording = self._camera.record_mode == 'Manual'
        except AmcrestError as error:
            _LOGGER.error(
                'Could not get %s camera attributes due to error: %s',
                self.name, error)

    # Other Camera method overrides

    def turn_off(self):
        """Turn off camera."""
        self._enable_video_stream(False)

    def turn_on(self):
        """Turn on camera."""
        self._enable_video_stream(True)

    # Utility methods

    def _enable_video_stream(self, enable):
        """Enable or disable camera video stream."""
        from amcrest import AmcrestError

        try:
            self._camera.video_enabled = enable
        except AmcrestError as error:
            _LOGGER.error(
                'Could not %s %s camera video stream due to error: %s',
                'enable' if enable else 'disable', self.name, error)
        else:
            self.is_streaming = enable
            self.schedule_update_ha_state()
