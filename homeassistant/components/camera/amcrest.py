"""
This component provides basic support for Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.amcrest/
"""
import asyncio
import logging

import aiohttp
import voluptuous as vol

import homeassistant.loader as loader
from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.components.ffmpeg import DATA_FFMPEG
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import (
    async_get_clientsession, async_aiohttp_proxy_web,
    async_aiohttp_proxy_stream)

REQUIREMENTS = ['amcrest==1.2.0']
DEPENDENCIES = ['ffmpeg']

_LOGGER = logging.getLogger(__name__)

CONF_RESOLUTION = 'resolution'
CONF_STREAM_SOURCE = 'stream_source'
CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEFAULT_NAME = 'Amcrest Camera'
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = 'high'
DEFAULT_STREAM_SOURCE = 'mjpeg'

NOTIFICATION_ID = 'amcrest_notification'
NOTIFICATION_TITLE = 'Amcrest Camera Setup'

RESOLUTION_LIST = {
    'high': 0,
    'low': 1,
}

STREAM_SOURCE_LIST = {
    'mjpeg': 0,
    'snapshot': 1,
    'rtsp': 2,
}

CONTENT_TYPE_HEADER = 'Content-Type'
TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_RESOLUTION, default=DEFAULT_RESOLUTION):
        vol.All(vol.In(RESOLUTION_LIST)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_STREAM_SOURCE, default=DEFAULT_STREAM_SOURCE):
        vol.All(vol.In(STREAM_SOURCE_LIST)),
    vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an Amcrest IP Camera."""
    from amcrest import AmcrestCamera
    camera = AmcrestCamera(
        config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_USERNAME), config.get(CONF_PASSWORD)).camera

    persistent_notification = loader.get_component('persistent_notification')
    try:
        camera.current_time
    # pylint: disable=broad-except
    except Exception as ex:
        _LOGGER.error("Unable to connect to Amcrest camera: %s", str(ex))
        persistent_notification.create(
            hass, 'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    add_devices([AmcrestCam(hass, config, camera)])
    return True


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, hass, device_info, camera):
        """Initialize an Amcrest camera."""
        super(AmcrestCam, self).__init__()
        self._camera = camera
        self._base_url = self._camera.get_base_url()
        self._name = device_info.get(CONF_NAME)
        self._ffmpeg = hass.data[DATA_FFMPEG]
        self._ffmpeg_arguments = device_info.get(CONF_FFMPEG_ARGUMENTS)
        self._resolution = RESOLUTION_LIST[device_info.get(CONF_RESOLUTION)]
        self._stream_source = STREAM_SOURCE_LIST[
            device_info.get(CONF_STREAM_SOURCE)
        ]
        self._token = self._auth = aiohttp.BasicAuth(
            device_info.get(CONF_USERNAME),
            password=device_info.get(CONF_PASSWORD)
        )

    def camera_image(self):
        """Return a still image reponse from the camera."""
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
