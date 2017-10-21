"""
This component provides basic support for Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.amcrest/
"""
import asyncio
import logging

from homeassistant.components.amcrest import (
    STREAM_SOURCE_LIST, TIMEOUT)
from homeassistant.components.camera import Camera
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_web,
    async_aiohttp_proxy_stream)

DEPENDENCIES = ['amcrest', 'ffmpeg']

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up an Amcrest IP Camera."""
    if discovery_info is None:
        return

    device = discovery_info['device']
    authentication = discovery_info['authentication']
    ffmpeg_arguments = discovery_info['ffmpeg_arguments']
    name = discovery_info['name']
    resolution = discovery_info['resolution']
    stream_source = discovery_info['stream_source']

    async_add_devices([
        AmcrestCam(hass,
                   name,
                   device,
                   authentication,
                   ffmpeg_arguments,
                   stream_source,
                   resolution)], True)

    return True


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, hass, name, camera, authentication,
                 ffmpeg_arguments, stream_source, resolution):
        """Initialize an Amcrest camera."""
        super(AmcrestCam, self).__init__()
        self._name = name
        self._camera = camera
        self._base_url = self._camera.get_base_url()
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = ffmpeg_arguments
        self._stream_source = stream_source
        self._resolution = resolution
        self._token = self._auth = authentication

    def camera_image(self):
        """Return a still image response from the camera."""
        # Send the request to snap a picture and return raw jpg data
        response = self._camera.snapshot(channel=self._resolution)
        return response.data

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        # The snapshot implementation is handled by the parent class
        if self._stream_source == STREAM_SOURCE_LIST['snapshot']:
            yield from super().handle_async_mjpeg_stream(request)
            return

        elif self._stream_source == STREAM_SOURCE_LIST['mjpeg']:
            # stream an MJPEG image stream directly from the camera
            websession = async_get_clientsession(self.hass)
            streaming_url = self._camera.mjpeg_url(typeno=self._resolution)
            stream_coro = websession.get(
                streaming_url, auth=self._token, timeout=TIMEOUT)

            yield from async_aiohttp_proxy_web(self.hass, request, stream_coro)

        else:
            # streaming via fmpeg
            from haffmpeg import CameraMjpeg

            streaming_url = self._camera.rtsp_url(typeno=self._resolution)
            stream = CameraMjpeg(self._ffmpeg.binary, loop=self.hass.loop)
            yield from stream.open_camera(
                streaming_url, extra_cmd=self._ffmpeg_arguments)

            yield from async_aiohttp_proxy_stream(
                self.hass, request, stream,
                'multipart/x-mixed-replace;boundary=ffserver')
            yield from stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
