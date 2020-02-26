"""Support for Amcrest IP cameras."""
from datetime import timedelta
import logging
import threading

import aiohttp
from amcrest import AmcrestError, Http, LoginError
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import DOMAIN as CAMERA
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_AUTHENTICATION,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SENSORS,
    CONF_USERNAME,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.exceptions import Unauthorized, UnknownUser
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.event import track_time_interval
from homeassistant.helpers.service import async_extract_entity_ids

from .binary_sensor import BINARY_SENSORS
from .camera import CAMERA_SERVICES, STREAM_SOURCE_LIST
from .const import (
    CAMERAS,
    COMM_RETRIES,
    COMM_TIMEOUT,
    DATA_AMCREST,
    DEVICES,
    DOMAIN,
    SERVICE_UPDATE,
)
from .helpers import service_signal
from .sensor import SENSORS

_LOGGER = logging.getLogger(__name__)

CONF_RESOLUTION = "resolution"
CONF_STREAM_SOURCE = "stream_source"
CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"
CONF_CONTROL_LIGHT = "control_light"

DEFAULT_NAME = "Amcrest Camera"
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = "high"
DEFAULT_ARGUMENTS = "-pred 1"
MAX_ERRORS = 5
RECHECK_INTERVAL = timedelta(minutes=1)

NOTIFICATION_ID = "amcrest_notification"
NOTIFICATION_TITLE = "Amcrest Camera Setup"

RESOLUTION_LIST = {"high": 0, "low": 1}

SCAN_INTERVAL = timedelta(seconds=10)

AUTHENTICATION_LIST = {"basic": "basic"}


def _has_unique_names(devices):
    names = [device[CONF_NAME] for device in devices]
    vol.Schema(vol.Unique())(names)
    return devices


AMCREST_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_AUTHENTICATION, default=HTTP_BASIC_AUTHENTICATION): vol.All(
            vol.In(AUTHENTICATION_LIST)
        ),
        vol.Optional(CONF_RESOLUTION, default=DEFAULT_RESOLUTION): vol.All(
            vol.In(RESOLUTION_LIST)
        ),
        vol.Optional(CONF_STREAM_SOURCE, default=STREAM_SOURCE_LIST[0]): vol.All(
            vol.In(STREAM_SOURCE_LIST)
        ),
        vol.Optional(CONF_FFMPEG_ARGUMENTS, default=DEFAULT_ARGUMENTS): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list, [vol.In(BINARY_SENSORS)]
        ),
        vol.Optional(CONF_SENSORS): vol.All(cv.ensure_list, [vol.In(SENSORS)]),
        vol.Optional(CONF_CONTROL_LIGHT, default=True): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [AMCREST_SCHEMA], _has_unique_names)},
    extra=vol.ALLOW_EXTRA,
)


class AmcrestChecker(Http):
    """amcrest.Http wrapper for catching errors."""

    def __init__(self, hass, name, host, port, user, password):
        """Initialize."""
        self._hass = hass
        self._wrap_name = name
        self._wrap_errors = 0
        self._wrap_lock = threading.Lock()
        self._wrap_login_err = False
        self._unsub_recheck = None
        super().__init__(
            host,
            port,
            user,
            password,
            retries_connection=COMM_RETRIES,
            timeout_protocol=COMM_TIMEOUT,
        )

    @property
    def available(self):
        """Return if camera's API is responding."""
        return self._wrap_errors <= MAX_ERRORS and not self._wrap_login_err

    def _start_recovery(self):
        dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._wrap_name))
        self._unsub_recheck = track_time_interval(
            self._hass, self._wrap_test_online, RECHECK_INTERVAL
        )

    def command(self, cmd, retries=None, timeout_cmd=None, stream=False):
        """amcrest.Http.command wrapper to catch errors."""
        try:
            ret = super().command(cmd, retries, timeout_cmd, stream)
        except LoginError as ex:
            with self._wrap_lock:
                was_online = self.available
                was_login_err = self._wrap_login_err
                self._wrap_login_err = True
            if not was_login_err:
                _LOGGER.error("%s camera offline: Login error: %s", self._wrap_name, ex)
            if was_online:
                self._start_recovery()
            raise
        except AmcrestError:
            with self._wrap_lock:
                was_online = self.available
                errs = self._wrap_errors = self._wrap_errors + 1
                offline = not self.available
            _LOGGER.debug("%s camera errs: %i", self._wrap_name, errs)
            if was_online and offline:
                _LOGGER.error("%s camera offline: Too many errors", self._wrap_name)
                self._start_recovery()
            raise
        with self._wrap_lock:
            was_offline = not self.available
            self._wrap_errors = 0
            self._wrap_login_err = False
        if was_offline:
            self._unsub_recheck()
            self._unsub_recheck = None
            _LOGGER.error("%s camera back online", self._wrap_name)
            dispatcher_send(self._hass, service_signal(SERVICE_UPDATE, self._wrap_name))
        return ret

    def _wrap_test_online(self, now):
        """Test if camera is back online."""
        _LOGGER.debug("Testing if %s back online", self._wrap_name)
        try:
            self.current_time
        except AmcrestError:
            pass


def setup(hass, config):
    """Set up the Amcrest IP Camera component."""
    hass.data.setdefault(DATA_AMCREST, {DEVICES: {}, CAMERAS: []})

    for device in config[DOMAIN]:
        name = device[CONF_NAME]
        username = device[CONF_USERNAME]
        password = device[CONF_PASSWORD]

        api = AmcrestChecker(
            hass, name, device[CONF_HOST], device[CONF_PORT], username, password
        )

        ffmpeg_arguments = device[CONF_FFMPEG_ARGUMENTS]
        resolution = RESOLUTION_LIST[device[CONF_RESOLUTION]]
        binary_sensors = device.get(CONF_BINARY_SENSORS)
        sensors = device.get(CONF_SENSORS)
        stream_source = device[CONF_STREAM_SOURCE]
        control_light = device.get(CONF_CONTROL_LIGHT)

        # currently aiohttp only works with basic authentication
        # only valid for mjpeg streaming
        if device[CONF_AUTHENTICATION] == HTTP_BASIC_AUTHENTICATION:
            authentication = aiohttp.BasicAuth(username, password)
        else:
            authentication = None

        hass.data[DATA_AMCREST][DEVICES][name] = AmcrestDevice(
            api,
            authentication,
            ffmpeg_arguments,
            stream_source,
            resolution,
            control_light,
        )

        discovery.load_platform(hass, CAMERA, DOMAIN, {CONF_NAME: name}, config)

        if binary_sensors:
            discovery.load_platform(
                hass,
                BINARY_SENSOR,
                DOMAIN,
                {CONF_NAME: name, CONF_BINARY_SENSORS: binary_sensors},
                config,
            )

        if sensors:
            discovery.load_platform(
                hass, SENSOR, DOMAIN, {CONF_NAME: name, CONF_SENSORS: sensors}, config
            )

    if not hass.data[DATA_AMCREST][DEVICES]:
        return False

    def have_permission(user, entity_id):
        return not user or user.permissions.check_entity(entity_id, POLICY_CONTROL)

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
                entity_id
                for entity_id in hass.data[DATA_AMCREST][CAMERAS]
                if have_permission(user, entity_id)
            ]

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_NONE:
            return []

        call_ids = await async_extract_entity_ids(hass, call)
        entity_ids = []
        for entity_id in hass.data[DATA_AMCREST][CAMERAS]:
            if entity_id not in call_ids:
                continue
            if not have_permission(user, entity_id):
                raise Unauthorized(
                    context=call.context, entity_id=entity_id, permission=POLICY_CONTROL
                )
            entity_ids.append(entity_id)
        return entity_ids

    async def async_service_handler(call):
        args = []
        for arg in CAMERA_SERVICES[call.service][2]:
            args.append(call.data[arg])
        for entity_id in await async_extract_from_service(call):
            async_dispatcher_send(hass, service_signal(call.service, entity_id), *args)

    for service, params in CAMERA_SERVICES.items():
        hass.services.register(DOMAIN, service, async_service_handler, params[0])

    return True


class AmcrestDevice:
    """Representation of a base Amcrest discovery device."""

    def __init__(
        self,
        api,
        authentication,
        ffmpeg_arguments,
        stream_source,
        resolution,
        control_light,
    ):
        """Initialize the entity."""
        self.api = api
        self.authentication = authentication
        self.ffmpeg_arguments = ffmpeg_arguments
        self.stream_source = stream_source
        self.resolution = resolution
        self.control_light = control_light
