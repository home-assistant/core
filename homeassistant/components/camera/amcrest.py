"""
This component provides basic support for Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.amcrest/
"""
import logging

from homeassistant.components.amcrest import (
    DATA_AMCREST, STREAM_SOURCE_LIST, TIMEOUT)
from homeassistant.components.camera import Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_web,
    async_aiohttp_proxy_stream)

DEPENDENCIES = ['amcrest', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    device_name = discovery_info[CONF_NAME]
    amcrest = hass.data[DATA_AMCREST][device_name]

    async_add_entities([AmcrestCam(hass, amcrest)], True)

    return True


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, hass, amcrest):
        """Initialize an Amcrest camera."""
        super(AmcrestCam, self).__init__()
        self._name = amcrest.name
        self._camera = amcrest.device
        self._base_url = self._camera.get_base_url()
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = amcrest.ffmpeg_arguments
        self._stream_source = amcrest.stream_source
        self._resolution = amcrest.resolution
        self._token = self._auth = amcrest.authentication

    def camera_image(self):
        """Return a still image response from the camera."""
        # Send the request to snap a picture and return raw jpg data
        response = self._camera.snapshot(channel=self._resolution)
        return response.data

    async def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        # The snapshot implementation is handled by the parent class
        if self._stream_source == STREAM_SOURCE_LIST['snapshot']:
            await super().handle_async_mjpeg_stream(request)
            return

        if self._stream_source == STREAM_SOURCE_LIST['mjpeg']:
            # stream an MJPEG image stream directly from the camera
            websession = async_get_clientsession(self.hass)
            streaming_url = self._camera.mjpeg_url(typeno=self._resolution)
            stream_coro = websession.get(
                streaming_url, auth=self._token, timeout=TIMEOUT)

            await async_aiohttp_proxy_web(self.hass, request, stream_coro)

        else:
            # streaming via fmpeg
            from haffmpeg import CameraMjpeg

            streaming_url = self._camera.rtsp_url(typeno=self._resolution)
            stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
            await stream.open_camera(
                streaming_url, extra_cmd=self._ffmpeg_arguments)

            await async_aiohttp_proxy_stream(
                self.hass, request, stream,
                'multipart/x-mixed-replace;boundary=ffserver')
            await stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
