"""Support for Amcrest IP cameras."""
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import DOMAIN as CAMERA
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.components.switch import DOMAIN as SWITCH
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_AUTHENTICATION, CONF_BINARY_SENSORS, CONF_HOST,
    CONF_NAME, CONF_PASSWORD, CONF_PORT, CONF_SCAN_INTERVAL, CONF_SENSORS,
    CONF_SWITCHES, CONF_USERNAME, ENTITY_MATCH_ALL, HTTP_BASIC_AUTHENTICATION)
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_extract_entity_ids

from .binary_sensor import BINARY_SENSORS
from .camera import CAMERA_SERVICES, STREAM_SOURCE_LIST
from .const import DOMAIN, DATA_AMCREST
from .helpers import service_signal
from .sensor import SENSOR_MOTION_DETECTOR, SENSORS
from .switch import SWITCHES

_LOGGER = logging.getLogger(__name__)

CONF_RESOLUTION = 'resolution'
CONF_STREAM_SOURCE = 'stream_source'
CONF_FFMPEG_ARGUMENTS = 'ffmpeg_arguments'

DEFAULT_NAME = 'Amcrest Camera'
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = 'high'
DEFAULT_ARGUMENTS = '-pred 1'

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
        vol.Optional(CONF_STREAM_SOURCE, default=STREAM_SOURCE_LIST[0]):
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
        stream_source = device[CONF_STREAM_SOURCE]

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

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_ALL:
            # Return all entity_ids user has permission to control.
            return [
                entity_id for entity_id in hass.data[DATA_AMCREST]['cameras']
                if have_permission(user, entity_id)
            ]

        call_ids = await async_extract_entity_ids(hass, call)
        entity_ids = []
        for entity_id in hass.data[DATA_AMCREST]['cameras']:
            if entity_id not in call_ids:
                continue
            if not have_permission(user, entity_id):
                raise Unauthorized(
                    context=call.context,
                    entity_id=entity_id,
                    permission=POLICY_CONTROL
                )
            entity_ids.append(entity_id)
        return entity_ids

    async def async_service_handler(call):
        args = []
        for arg in CAMERA_SERVICES[call.service][2]:
            args.append(call.data[arg])
        for entity_id in await async_extract_from_service(call):
            async_dispatcher_send(
                hass,
                service_signal(call.service, entity_id),
                *args
            )

    for service, params in CAMERA_SERVICES.items():
        hass.services.async_register(
            DOMAIN, service, async_service_handler, params[0])

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
