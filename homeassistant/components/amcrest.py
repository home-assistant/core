"""
This component provides basic support for Amcrest IP cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/amcrest/
"""
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD,
    CONF_SENSORS, CONF_SCAN_INTERVAL, HTTP_BASIC_AUTHENTICATION)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['amcrest==1.2.1']
DEPENDENCIES = ['ffmpeg']

_LOGGER = logging.getLogger(__name__)

CONF_AUTHENTICATION = 'authentication'
CONF_RESOLUTION = 'resolution'
CONF_STREAM_SOURCE = 'stream_source'
CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEFAULT_NAME = 'Amcrest Camera'
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = 'high'
DEFAULT_STREAM_SOURCE = 'snapshot'
TIMEOUT = 10

DATA_AMCREST = 'amcrest'
DOMAIN = 'amcrest'

NOTIFICATION_ID = 'amcrest_notification'
NOTIFICATION_TITLE = 'Amcrest Camera Setup'

RESOLUTION_LIST = {
    'high': 0,
    'low': 1,
}

SCAN_INTERVAL = timedelta(seconds=10)

AUTHENTICATION_LIST = {
    'basic': 'basic'
}

STREAM_SOURCE_LIST = {
    'mjpeg': 0,
    'snapshot': 1,
    'rtsp': 2,
}

# Sensor types are defined like: Name, units, icon
SENSORS = {
    'motion_detector': ['Motion Detected', None, 'mdi:run'],
    'sdcard': ['SD Used', '%', 'mdi:sd'],
    'ptz_preset': ['PTZ Preset', None, 'mdi:camera-iris'],
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION):
            vol.All(vol.In(AUTHENTICATION_LIST)),
        vol.Optional(CONF_RESOLUTION, default=DEFAULT_RESOLUTION):
            vol.All(vol.In(RESOLUTION_LIST)),
        vol.Optional(CONF_STREAM_SOURCE, default=DEFAULT_STREAM_SOURCE):
            vol.All(vol.In(STREAM_SOURCE_LIST)),
        vol.Optional(CONF_FFMPEG_ARGUMENTS): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
        vol.Optional(CONF_SENSORS, default=None):
            vol.All(cv.ensure_list, [vol.In(SENSORS)]),
    })])
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Amcrest IP Camera component."""
    from amcrest import AmcrestCamera

    hass.data[DATA_AMCREST] = {}
    amcrest_cams = config[DOMAIN]

    for device in amcrest_cams:
        camera = AmcrestCamera(device.get(CONF_HOST),
                               device.get(CONF_PORT),
                               device.get(CONF_USERNAME),
                               device.get(CONF_PASSWORD)).camera
        try:
            camera.current_time

        except (ConnectTimeout, HTTPError) as ex:
            _LOGGER.error("Unable to connect to Amcrest camera: %s", str(ex))
            hass.components.persistent_notification.create(
                'Error: {}<br />'
                'You will need to restart hass after fixing.'
                ''.format(ex),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            return False

        ffmpeg_arguments = device.get(CONF_FFMPEG_ARGUMENTS)
        name = device.get(CONF_NAME)
        resolution = RESOLUTION_LIST[device.get(CONF_RESOLUTION)]
        sensors = device.get(CONF_SENSORS)
        stream_source = STREAM_SOURCE_LIST[device.get(CONF_STREAM_SOURCE)]

        username = device.get(CONF_USERNAME)
        password = device.get(CONF_PASSWORD)

        # currently aiohttp only works with basic authentication
        # only valid for mjpeg streaming
        if username is not None and password is not None:
            if device.get(CONF_AUTHENTICATION) == HTTP_BASIC_AUTHENTICATION:
                authentication = aiohttp.BasicAuth(username, password)
            else:
                authentication = None

        hass.data[DATA_AMCREST][name] = AmcrestDevice(
            camera, name, authentication, ffmpeg_arguments, stream_source,
            resolution)

        discovery.load_platform(
            hass, 'camera', DOMAIN, {
                CONF_NAME: name,
            }, config)

        if sensors:
            discovery.load_platform(
                hass, 'sensor', DOMAIN, {
                    CONF_NAME: name,
                    CONF_SENSORS: sensors,
                }, config)

    return True


class AmcrestDevice(object):
    """Representation of a base Amcrest discovery device."""

    def __init__(self, camera, name, authentication, ffmpeg_arguments,
                 stream_source, resolution):
        """Initialize the entity."""
        self.device = camera
        self.name = name
        self.authentication = authentication
        self.ffmpeg_arguments = ffmpeg_arguments
        self.stream_source = stream_source
        self.resolution = resolution
