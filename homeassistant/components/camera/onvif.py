"""
Support for ONVIF Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.onvif/
"""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT,
    ATTR_ENTITY_ID, ATTR_DIR_H, ATTR_DIR_V, ATTR_ZOOM)
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA, DOMAIN
from homeassistant.components.ffmpeg import (
    DATA_FFMPEG)
from homeassistant.config import load_yaml_config_file
from homeassistant.helpers.entity_component import EntityComponent
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['onvif-py3==0.1.3',
                'suds-py3==1.3.3.0',
                'http://github.com/tgaugry/suds-passworddigest-py3'
                '/archive/86fc50e39b4d2b8997481967d6a7fe1c57118999.zip'
                '#suds-passworddigest-py3==0.1.2a']
DEPENDENCIES = ['ffmpeg']
DEFAULT_NAME = 'ONVIF Camera'
DEFAULT_PORT = 5000
DEFAULT_USERNAME = 'admin'
DEFAULT_PASSWORD = '888888'

DIR_UP = "UP"
DIR_DOWN = "DOWN"
DIR_LEFT = "LEFT"
DIR_RIGHT = "RIGHT"

ZOOM_OUT = "ZOOM_OUT"
ZOOM_IN = "ZOOM_IN"

SERVICE_PTZ = "PTZ"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})

SERVICE_PTZ_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_DIR_H: vol.In([DIR_LEFT, DIR_RIGHT]),
    ATTR_DIR_V: vol.In([DIR_UP, DIR_DOWN]),
    ATTR_ZOOM: vol.In([ZOOM_OUT, ZOOM_IN])
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a ONVIF camera."""
    if not hass.data[DATA_FFMPEG].async_run_test(config.get(CONF_HOST)):
        return

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entities = []

    def handle_ptz(service):
        dir_v = service.data.get(ATTR_DIR_V, None)
        if dir_v:
            dir_v = dir_v.upper()
        dir_h = service.data.get(ATTR_DIR_H, None)
        if dir_h:
            dir_h = dir_h.upper()
        zoom = service.data.get(ATTR_ZOOM, None)
        if zoom:
            zoom = zoom.upper()
        target_cameras = component.extract_from_service(service)
        req = None
        for camera in target_cameras:
            if not camera._ptz:
                continue
            if not req:
                req = camera._ptz.create_type('ContinuousMove')
                if dir_v == DIR_UP:
                    req.Velocity.PanTilt._y = 1
                elif dir_v == DIR_DOWN:
                    req.Velocity.PanTilt._y = -1
                if dir_h == DIR_LEFT:
                    req.Velocity.PanTilt._x = -1
                elif dir_h == DIR_RIGHT:
                    req.Velocity.PanTilt._x = 1
                if zoom == ZOOM_IN:
                    req.Velocity.Zoom._x = 1
                elif zoom == ZOOM_OUT:
                    req.Velocity.Zoom._x = -1
            camera._ptz.ContinuousMove(req)


    descriptions = load_yaml_config_file(
            os.path.join(os.path.dirname(__file__), 'services.yaml'))

    hass.services.async_register(DOMAIN, SERVICE_PTZ,
            handle_ptz, descriptions.get(SERVICE_PTZ),
            schema=SERVICE_PTZ_SCHEMA)
    entities.append(ONVIFCamera(hass, config))
    yield from component.async_add_entities(entities)


class ONVIFCamera(Camera):
    """An implementation of an ONVIF camera."""

    def __init__(self, hass, config):
        """Initialize a ONVIF camera."""
        from onvif import ONVIFService
        import onvif
        super().__init__()

        self._name = config.get(CONF_NAME)
        self._ffmpeg_arguments = '-q:v 2'
        try:
            self._ptz = ONVIFService(
                'http://{}:{}/onvif/device_service'.format(
                    config.get(CONF_HOST), config.get(CONF_PORT)),
                config.get(CONF_USERNAME),
                config.get(CONF_PASSWORD),
                '{}/wsdl/ptz.wsdl'.format(os.path.dirname(onvif.__file__))
            )
        except onvif.exceptions.ONVIFError:
            self._ptz = None
            _LOGGER.warning("PTZ is not supported by camera")
        media = ONVIFService(
            'http://{}:{}/onvif/device_service'.format(
                config.get(CONF_HOST), config.get(CONF_PORT)),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            '{}/wsdl/media.wsdl'.format(os.path.dirname(onvif.__file__))
        )
        self._input = media.GetStreamUri().Uri
        _LOGGER.debug("ONVIF Camera Using the following URL for %s: %s",
                      self._name, self._input)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        from haffmpeg import ImageFrame, IMAGE_JPEG
        ffmpeg = ImageFrame(
            self.hass.data[DATA_FFMPEG].binary, loop=self.hass.loop)

        image = yield from asyncio.shield(ffmpeg.get_image(
            self._input, output_format=IMAGE_JPEG,
            extra_cmd=self._ffmpeg_arguments), loop=self.hass.loop)
        return image

    @asyncio.coroutine
    def handle_async_mjpeg_stream(self, request):
        """Generate an HTTP MJPEG stream from the camera."""
        from haffmpeg import CameraMjpeg

        stream = CameraMjpeg(self.hass.data[DATA_FFMPEG].binary,
                             loop=self.hass.loop)
        yield from stream.open_camera(
            self._input, extra_cmd=self._ffmpeg_arguments)

        yield from async_aiohttp_proxy_stream(
            self.hass, request, stream,
            'multipart/x-mixed-replace;boundary=ffserver')
        yield from stream.close()

    @property
    def name(self):
        """Return the name of this camera."""
        return self._name
