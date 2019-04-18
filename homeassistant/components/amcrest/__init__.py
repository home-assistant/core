"""Support for Amcrest IP cameras."""
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import (
    CAMERA_SERVICE_SCHEMA, DOMAIN as CAMERA)
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_AUTHENTICATION, CONF_BINARY_SENSORS, CONF_HOST,
    CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SENSORS,
    CONF_SWITCHES, CONF_USERNAME, ENTITY_MATCH_ALL, HTTP_BASIC_AUTHENTICATION)
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service import async_extract_entity_ids

_LOGGER = logging.getLogger(__name__)

CONF_RESOLUTION = 'resolution'
CONF_STREAM_SOURCE = 'stream_source'
CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEFAULT_NAME = 'Amcrest Camera'
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = 'high'
DEFAULT_STREAM_SOURCE = 'snapshot'
DEFAULT_ARGUMENTS = '-pred 1'
TIMEOUT = 10

DOMAIN = 'amcrest'
DATA_AMCREST = DOMAIN

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

BINARY_SENSORS = {
    'motion_detected': 'Motion Detected'
}

# Sensor types are defined like: Name, units, icon
SENSOR_MOTION_DETECTOR = 'motion_detector'
SENSORS = {
    SENSOR_MOTION_DETECTOR: ['Motion Detected', None, 'mdi:run'],
    'sdcard': ['SD Used', '%', 'mdi:sd'],
    'ptz_preset': ['PTZ Preset', None, 'mdi:camera-iris'],
}

# Switch types are defined like: Name, icon
SWITCHES = {
    'motion_detection': ['Motion Detection', 'mdi:run-fast'],
    'motion_recording': ['Motion Recording', 'mdi:record-rec']
}


def _deprecated_sensor_values(sensors):
    if SENSOR_MOTION_DETECTOR in sensors:
        _LOGGER.warning(
            "The 'sensors' option value '%s' is deprecated, "
            "please remove it from your configuration and use "
            "the 'binary_sensors' option with value 'motion_detected' "
            "instead.", SENSOR_MOTION_DETECTOR)
    return sensors


def _deprecated_switches(config):
    if CONF_SWITCHES in config:
        _LOGGER.warning(
            "The 'switches' option (with value %s) is deprecated, "
            "please remove it from your configuration and use "
            "camera services and attributes instead.",
            config[CONF_SWITCHES])
    return config


def _has_unique_names(devices):
    names = [device[CONF_NAME] for device in devices]
    vol.Schema(vol.Unique())(names)
    return devices


AMCREST_SCHEMA = vol.All(
    vol.Schema({
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
        vol.Optional(CONF_FFMPEG_ARGUMENTS, default=DEFAULT_ARGUMENTS):
            cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
        vol.Optional(CONF_BINARY_SENSORS):
            vol.All(cv.ensure_list, [vol.In(BINARY_SENSORS)]),
        vol.Optional(CONF_SENSORS):
            vol.All(cv.ensure_list, [vol.In(SENSORS)],
                    _deprecated_sensor_values),
        vol.Optional(CONF_SWITCHES):
            vol.All(cv.ensure_list, [vol.In(SWITCHES)]),
    }),
    _deprecated_switches
)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [AMCREST_SCHEMA], _has_unique_names)
}, extra=vol.ALLOW_EXTRA)

SERVICE_ENABLE_RECORDING = 'enable_recording'
SERVICE_DISABLE_RECORDING = 'disable_recording'
SERVICE_ENABLE_AUDIO = 'enable_audio'
SERVICE_DISABLE_AUDIO = 'disable_audio'
SERVICE_ENABLE_MOTION_RECORDING = 'enable_motion_recording'
SERVICE_DISABLE_MOTION_RECORDING = 'disable_motion_recording'
SERVICE_GOTO_PRESET = 'goto_preset'
SERVICE_SET_COLOR_BW = 'set_color_bw'
SERVICE_START_TOUR = 'start_tour'
SERVICE_STOP_TOUR = 'stop_tour'

ATTR_PRESET = 'preset'
ATTR_COLOR_BW = 'color_bw'

CBW_COLOR = 'color'
CBW_AUTO = 'auto'
CBW_BW = 'bw'
CBW = [CBW_COLOR, CBW_AUTO, CBW_BW]

SERVICE_GOTO_PRESET_SCHEMA = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_PRESET): vol.All(vol.Coerce(int), vol.Range(min=1)),
})
SERVICE_SET_COLOR_BW_SCHEMA = CAMERA_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_COLOR_BW): vol.In(CBW),
})


def setup(hass, config):
    """Set up the Amcrest IP Camera component."""
    from amcrest import AmcrestCamera, AmcrestError

    hass.data.setdefault(DATA_AMCREST, {'devices': {}, 'cameras': []})
    devices = config[DOMAIN]

    for device in devices:
        name = device[CONF_NAME]
        username = device[CONF_USERNAME]
        password = device[CONF_PASSWORD]

        try:
            api = AmcrestCamera(device[CONF_HOST],
                                device[CONF_PORT],
                                username,
                                password).camera
            # pylint: disable=pointless-statement
            # Test camera communications.
            api.current_time

        except AmcrestError as ex:
            _LOGGER.error("Unable to connect to %s camera: %s", name, str(ex))
            hass.components.persistent_notification.create(
                'Error: {}<br />'
                'You will need to restart hass after fixing.'
                ''.format(ex),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            continue

        ffmpeg_arguments = device[CONF_FFMPEG_ARGUMENTS]
        resolution = RESOLUTION_LIST[device[CONF_RESOLUTION]]
        binary_sensors = device.get(CONF_BINARY_SENSORS)
        sensors = device.get(CONF_SENSORS)
        switches = device.get(CONF_SWITCHES)
        stream_source = STREAM_SOURCE_LIST[device[CONF_STREAM_SOURCE]]

        # currently aiohttp only works with basic authentication
        # only valid for mjpeg streaming
        if device[CONF_AUTHENTICATION] == HTTP_BASIC_AUTHENTICATION:
            authentication = aiohttp.BasicAuth(username, password)
        else:
            authentication = None

        hass.data[DATA_AMCREST]['devices'][name] = AmcrestDevice(
            api, authentication, ffmpeg_arguments, stream_source,
            resolution)

        discovery.load_platform(
            hass, CAMERA, DOMAIN, {
                CONF_NAME: name,
            }, config)

        if binary_sensors:
            discovery.load_platform(
                hass, BINARY_SENSOR, DOMAIN, {
                    CONF_NAME: name,
                    CONF_BINARY_SENSORS: binary_sensors
                }, config)

        if sensors:
            discovery.load_platform(
                hass, SENSOR, DOMAIN, {
                    CONF_NAME: name,
                    CONF_SENSORS: sensors,
                }, config)

        if switches:
            discovery.load_platform(
                hass, SWITCH, DOMAIN, {
                    CONF_NAME: name,
                    CONF_SWITCHES: switches
                }, config)

    if not hass.data[DATA_AMCREST]['devices']:
        return False

    def have_permission(user, entity_id):
        return not user or user.permissions.check_entity(
            entity_id, POLICY_CONTROL)

    async def async_extract_from_service(call):
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(context=call.context)
        else:
            user = None
        entity_ids = call.data.get(ATTR_ENTITY_ID)

        if entity_ids == ENTITY_MATCH_ALL:
            # Return all entities user has permission to control.
            return [entity for entity in hass.data[DATA_AMCREST]['cameras']
                    if have_permission(user, entity.entity_id)
                    and entity.available]

        entity_ids = await async_extract_entity_ids(hass, call)
        entities = []
        for entity in hass.data[DATA_AMCREST]['cameras']:
            if entity.entity_id not in entity_ids:
                continue
            if not have_permission(user, entity.entity_id):
                raise Unauthorized(
                    context=call.context,
                    entity_id=entity.entity_id,
                    permission=POLICY_CONTROL
                )
            if entity.available:
                entities.append(entity)
        return entities

    async def async_service_handler(call):
        for camera in await async_extract_from_service(call):
            await getattr(camera, handled_services[call.service])()

    async def async_goto_preset(call):
        preset = call.data[ATTR_PRESET]
        for camera in await async_extract_from_service(call):
            await camera.async_goto_preset(preset)

    async def async_set_color_bw(call):
        cbw = call.data[ATTR_COLOR_BW]
        for camera in await async_extract_from_service(call):
            await camera.async_set_color_bw(cbw)

    handled_services = {
        SERVICE_ENABLE_RECORDING: 'async_enable_recording',
        SERVICE_DISABLE_RECORDING: 'async_disable_recording',
        SERVICE_ENABLE_AUDIO: 'async_enable_audio',
        SERVICE_DISABLE_AUDIO: 'async_disable_audio',
        SERVICE_ENABLE_MOTION_RECORDING: 'async_enable_motion_recording',
        SERVICE_DISABLE_MOTION_RECORDING: 'async_disable_motion_recording',
        SERVICE_START_TOUR: 'async_start_tour',
        SERVICE_STOP_TOUR: 'async_stop_tour',
    }

    for service in handled_services:
        hass.services.async_register(
            DOMAIN, service, async_service_handler, CAMERA_SERVICE_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_GOTO_PRESET, async_goto_preset,
        SERVICE_GOTO_PRESET_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_SET_COLOR_BW, async_set_color_bw,
        SERVICE_SET_COLOR_BW_SCHEMA)

    return True


class AmcrestDevice:
    """Representation of a base Amcrest discovery device."""

    def __init__(self, api, authentication, ffmpeg_arguments,
                 stream_source, resolution):
        """Initialize the entity."""
        self.api = api
        self.authentication = authentication
        self.ffmpeg_arguments = ffmpeg_arguments
        self.stream_source = stream_source
        self.resolution = resolution
