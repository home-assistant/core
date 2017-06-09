"""
Support for ONVIF Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.onvif/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_USERNAME, CONF_PASSWORD, CONF_PORT)
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA
from homeassistant.components.ffmpeg import (
    DATA_FFMPEG, CONF_INPUT, CONF_EXTRA_ARGUMENTS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['onvif-py3==0.1.3','suds-py3==1.3.3.0','http://github.com/tgaugry/suds-passworddigest-py3/archive/86fc50e39b4d2b8997481967d6a7fe1c57118999.zip#suds-passworddigest-py3==0.1.2a']
DEPENDENCIES = ['ffmpeg']
DEFAULT_NAME = 'ONVIF Camera'
DEFAULT_PORT = 5000
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = '888888'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_INPUT): cv.string,
    vol.Optional(CONF_EXTRA_ARGUMENTS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a ONVIF camera."""
    if not hass.data[DATA_FFMPEG].async_run_test(config.get(CONF_INPUT)):
        return
    async_add_devices([ONVIFCamera(hass, config)])


class ONVIFCamera(Camera):
    """An implementation of an ONVIF camera."""

    def __init__(self, hass, config):
        """Initialize a ONVIF camera."""
        from onvif import ONVIFService
        super().__init__()

        self._manager = hass.data[DATA_FFMPEG]
        self._name = config.get(CONF_NAME)
        self._input = config.get(CONF_INPUT)
        self._extra_arguments = config.get(CONF_EXTRA_ARGUMENTS)
        port = config.get(CONF_PORT)
        wsdl = hass.config.config_dir + '/deps/onvif/wsdl/'
        self._base_url = 'http://{}:{}/'.format(self._input, port)
        device_url = self._base_url + 'onvif/device_service'
        self._username = config.get(CONF_USERNAME)
        self._password = config.get(CONF_PASSWORD)
        media = ONVIFService(device_url,self._username, self._password, wsdl + 'media.wsdl')
        media_profile = media.GetProfiles()[0]
        self._input = media.GetStreamUri().Uri
        _LOGGER.debug("Using the following URL for %s: %s",
                     self._name, self._input)
        _LOGGER.debug("Using the base URL for %s: %s",
                     self._name, self._base_url)
        _LOGGER.debug("Using the device URL for %s: %s",
                     self._name, device_url)
        _LOGGER.debug("WSDL for %s: %s",
                     self._name, wsdl)
        _LOGGER.debug("Login details for %s: %s %s",
                     self._name, self._username, self._password)


    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(self._manager.binary, loop=self.hass.loop)

        image = yield from ffmpeg.get_image(
            self._input, output_format=IMAGE_JPEG,
            extra_cmd=self._extra_arguments)
        return image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg

        stream = CameraMjpeg(self._manager.binary, loop=self.hass.loop)
        yield from stream.open_camera(
            self._input, extra_cmd=self._extra_arguments)

        yield from async_aiohttp_proxy_stream(
            self.hass, request, stream,
            'multipart/x-mixed-replace;boundary=ffserver')
        yield from stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
