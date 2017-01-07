"""
This component provides basic support for Amcrest IP cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.amcrest/
"""
import asyncio
import logging

import aiohttp
from aiohttp import web
from aiohttp.web_exceptions import HTTPGatewayTimeout
import async_timeout
import voluptuous as vol

import homeassistant.loader as loader
from homeassistant.components.camera import (Camera, PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession

REQUIREMENTS = ['amcrest==1.0.0']

_LOGGER = logging.getLogger(__name__)

CONF_RESOLUTION = 'resolution'
CONF_STREAM_SOURCE = 'stream_source'

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
    'snapshot': 1
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
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an Amcrest IP Camera."""
    from amcrest import AmcrestCamera
    data = AmcrestCamera(
        config.get(CONF_HOST), config.get(CONF_PORT),
        config.get(CONF_USERNAME), config.get(CONF_PASSWORD))

    persistent_notification = loader.get_component('persistent_notification')
    try:
        data.camera.current_time
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

    add_devices([AmcrestCam(hass, config, data)])
    return True


class AmcrestCam(Camera):
    """An implementation of an Amcrest IP camera."""

    def __init__(self, hass, device_info, data):
        """Initialize an Amcrest camera."""
        super(AmcrestCam, self).__init__()
        self._base_url = '%s://%s:%s/cgi-bin' % (
            'http',
            device_info.get(CONF_HOST),
            device_info.get(CONF_PORT)
        )
        self._data = data
        self._hass = hass
        self._name = device_info.get(CONF_NAME)
        self._resolution = RESOLUTION_LIST[device_info.get(CONF_RESOLUTION)]
        self._stream_source = STREAM_SOURCE_LIST[
            device_info.get(CONF_STREAM_SOURCE)
        ]
        self._token = self._auth = aiohttp.BasicAuth(
            device_info.get(CONF_USERNAME),
            password=device_info.get(CONF_PASSWORD)
        )
        self._websession = async_create_clientsession(hass)

    def camera_image(self):
        """Return a still image reponse from the camera."""
        # Send the request to snap a picture and return raw jpg data
        response = self._data.camera.snapshot(channel=self._resolution)
        return response.data

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Return an MJPEG stream."""
        # The snapshot implementation is handled by the parent class
        if self._stream_source == STREAM_SOURCE_LIST['snapshot']:
            yield from super().handle_async_mjpeg_stream(request)
            return

        # Otherwise, stream an MJPEG image stream directly from the camera
        streaming_url = '%s/mjpg/video.cgi?channel=0&subtype=%d' % (
            self._base_url,
            self._resolution
        )

        stream = None
        response = None
        try:
            with async_timeout.timeout(TIMEOUT, loop=self.hass.loop):
                stream = yield from self._websession.get(
                    streaming_url,
                    auth=self._token,
                    timeout=TIMEOUT
                )
            response = web.StreamResponse()
            response.content_type = stream.headers.get(CONTENT_TYPE_HEADER)

            yield from response.prepare(request)

            while True:
                data = yield from stream.content.read(16384)
                if not data:
                    break
                response.write(data)

        except (asyncio.TimeoutError, aiohttp.errors.ClientError):
            _LOGGER.exception("Error on %s", streaming_url)
            raise HTTPGatewayTimeout()

        finally:
            if stream is not None:
                self.hass.async_add_job(stream.release())
            if response is not None:
                yield from response.write_eof()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
