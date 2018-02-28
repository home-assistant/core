"""
Support for ONVIF Cameras with FFmpeg as decoder.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.onvif/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_PORT,
    ATTR_ENTITY_ID)
from homeassistant.components.camera import Camera, PLATFORM_SCHEMA, DOMAIN
from homeassistant.components.ffmpeg import (
    DATA_FFMPEG, CONF_EXTRA_ARGUMENTS)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.aiohttp_client import (
    async_aiohttp_proxy_stream)
from homeassistant.helpers.service import extract_entity_ids

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
DEFAULT_ARGUMENTS = '-q:v 2'

ATTR_PAN = "pan"
ATTR_TILT = "tilt"
ATTR_ZOOM = "zoom"

DIR_UP = "UP"
DIR_DOWN = "DOWN"
DIR_LEFT = "LEFT"
DIR_RIGHT = "RIGHT"
ZOOM_OUT = "ZOOM_OUT"
ZOOM_IN = "ZOOM_IN"

SERVICE_PTZ = "onvif_ptz"

ONVIF_DATA = "onvif"
ENTITIES = "entities"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PASSWORD, default=DEFAULT_PASSWORD): cv.string,
    vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_EXTRA_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
})

SERVICE_PTZ_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.entity_ids,
    ATTR_PAN: vol.In([DIR_LEFT, DIR_RIGHT]),
    ATTR_TILT: vol.In([DIR_UP, DIR_DOWN]),
    ATTR_ZOOM: vol.In([ZOOM_OUT, ZOOM_IN])
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up a ONVIF camera."""
    if not hass.data[DATA_FFMPEG].async_run_test(config.get(CONF_HOST)):
        return

    def handle_ptz(service):
        """Handle PTZ service call."""
        pan = service.data.get(ATTR_PAN, None)
        tilt = service.data.get(ATTR_TILT, None)
        zoom = service.data.get(ATTR_ZOOM, None)
        all_cameras = hass.data[ONVIF_DATA][ENTITIES]
        entity_ids = extract_entity_ids(hass, service)
        target_cameras = []
        if not entity_ids:
            target_cameras = all_cameras
        else:
            target_cameras = [camera for camera in all_cameras
                              if camera.entity_id in entity_ids]
        for camera in target_cameras:
            camera.perform_ptz(pan, tilt, zoom)

    hass.services.async_register(DOMAIN, SERVICE_PTZ, handle_ptz,
                                 schema=SERVICE_PTZ_SCHEMA)
    async_add_devices([ONVIFHassCamera(hass, config)])


class ONVIFHassCamera(Camera):
    """An implementation of an ONVIF camera."""

    def __init__(self, hass, config):
        """Initialize a ONVIF camera."""
        from onvif import ONVIFCamera, exceptions
        super().__init__()

        self._name = config.get(CONF_NAME)
        self._ffmpeg_arguments = config.get(CONF_EXTRA_ARGUMENTS)
        self._input = None
        camera = None
        try:
            _LOGGER.debug("Connecting with ONVIF Camera: %s on port %s",
                          config.get(CONF_HOST), config.get(CONF_PORT))
            camera = ONVIFCamera(
                config.get(CONF_HOST), config.get(CONF_PORT),
                config.get(CONF_USERNAME), config.get(CONF_PASSWORD)
            )
            media_service = camera.create_media_service()
            stream_uri = media_service.GetStreamUri(
                {'StreamSetup': {'Stream': 'RTP-Unicast', 'Transport': 'RTSP'}}
                )
            self._input = stream_uri.Uri.replace(
                'rtsp://', 'rtsp://{}:{}@'.format(
                    config.get(CONF_USERNAME),
                    config.get(CONF_PASSWORD)), 1)
            _LOGGER.debug(
                "ONVIF Camera Using the following URL for %s: %s",
                self._name, self._input)
        except Exception as err:
            _LOGGER.error("Unable to communicate with ONVIF Camera: %s", err)
            raise
        try:
            self._ptz = camera.create_ptz_service()
        except exceptions.ONVIFError as err:
            self._ptz = None
            _LOGGER.warning("Unable to setup PTZ for ONVIF Camera: %s", err)

    def perform_ptz(self, pan, tilt, zoom):
        """Perform a PTZ action on the camera."""
        if self._ptz:
            pan_val = 1 if pan == DIR_RIGHT else -1 if pan == DIR_LEFT else 0
            tilt_val = 1 if tilt == DIR_UP else -1 if tilt == DIR_DOWN else 0
            zoom_val = 1 if zoom == ZOOM_IN else -1 if zoom == ZOOM_OUT else 0
            req = {"Velocity": {
                "PanTilt": {"_x": pan_val, "_y": tilt_val},
                "Zoom": {"_x": zoom_val}}}
            self._ptz.ContinuousMove(req)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Callback when entity is added to hass."""
        if ONVIF_DATA not in self.hass.data:
            self.hass.data[ONVIF_DATA] = {}
            self.hass.data[ONVIF_DATA][ENTITIES] = []
        self.hass.data[ONVIF_DATA][ENTITIES].append(self)

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
