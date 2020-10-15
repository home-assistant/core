"""Support for Amcrest IP cameras."""
import logging
import threading

import aiohttp
from amcrest import AmcrestError

from homeassistant import config_entries
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import DOMAIN as CAMERA
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_AUTHENTICATION,
    CONF_BINARY_SENSORS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SENSORS,
    CONF_USERNAME,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import callback
from homeassistant.exceptions import Unauthorized, UnknownUser

# from homeassistant.helpers import discovery
# import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.service import async_extract_entity_ids

# from .sensor import SENSORS
from .amcrest_checker import AmcrestChecker
from .binary_sensor import BINARY_POLLED_SENSORS, BINARY_SENSORS
from .camera import CAMERA_SERVICES
from .const import (
    CAMERAS,
    CONF_CONTROL_LIGHT,
    CONF_EVENTS,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RESOLUTION,
    CONF_STREAM_SOURCE,
    DATA_AMCREST,
    DEFAULT_AUTHENTICATION,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DEFAULT_STREAM_SOURCE,
    DEVICES,
    DOMAIN,
    SENSOR_EVENT_CODE,
    SERVICE_EVENT,
)
from .helpers import service_signal

# import voluptuous as vol





_LOGGER = logging.getLogger(__name__)


def _monitor_events(hass, name, api, event_codes):
    if "All" in event_codes["events"]:
        event_codes_list = "All"
    else:
        event_codes_list = ",".join(
            list(dict.fromkeys(event_codes["binary_sensors"] + event_codes["events"]))
        )
    while True:
        api.available_flag.wait()
        try:
            for code, payload in api.event_actions(event_codes_list, retries=5):
                _LOGGER.debug("Captured event: %s -- %s", code, payload)
                if code in event_codes["binary_sensors"]:
                    # Management of the different actions for binary sensors
                    start = bool(
                        payload["action"] == "Start" or payload["action"] == "Pulse"
                    )
                    signal = service_signal(SERVICE_EVENT, name, code)
                    _LOGGER.debug("Sending signal: '%s': %s", signal, start)
                    dispatcher_send(hass, signal, start)

                if code in event_codes["events"] or "All" in event_codes["events"]:
                    _LOGGER.debug(
                        "Sending event to bus, event name: %s, payload: %s",
                        code,
                        payload,
                    )
                    hass.bus.fire(DOMAIN + "." + code, payload)

        except AmcrestError as error:
            _LOGGER.warning(
                "Error while processing events from %s camera: %r", name, error
            )


def _start_event_monitor(hass, name, api, event_codes):
    thread = threading.Thread(
        target=_monitor_events,
        name=f"Amcrest {name}",
        args=(hass, name, api, event_codes),
        daemon=True,
    )
    thread.start()


async def async_setup(hass, config):
    """Old way to set up Amcrest devices."""

    # Import from yaml if exist
    conf = config.get(DOMAIN)
    if conf is not None:
        for entry in conf:
            # Only import if we haven't before.
            config_entry = _async_find_matching_config_entry(hass)
            if not config_entry:
                if CONF_NAME not in entry:
                    entry.update({CONF_NAME: DEFAULT_NAME})
                if CONF_PORT not in entry:
                    entry.update({CONF_PORT: DEFAULT_PORT})
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )

    return True


@callback
def _async_find_matching_config_entry(hass):
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.source == config_entries.SOURCE_IMPORT:
            return entry


async def async_setup_entry(hass, config_entry):
    """Set up the Amcrest IP Camera component."""
    hass.data.setdefault(DATA_AMCREST, {DEVICES: {}, CAMERAS: []})

    name = config_entry.data[CONF_NAME]
    _LOGGER.debug("read config entry name : %s", name)
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    api = AmcrestChecker(
        hass,
        name,
        config_entry.data[CONF_HOST],
        config_entry.data[CONF_PORT],
        username,
        password,
    )

    ffmpeg_arguments = config_entry.options.get(
        CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
    )
    resolution = config_entry.options.get(CONF_RESOLUTION, DEFAULT_RESOLUTION)
    _LOGGER.debug("read config entry resolution : %s", resolution)
    binary_sensors = config_entry.options.get(CONF_BINARY_SENSORS, [])
    _LOGGER.debug("read binarey_sensor: %s", binary_sensors)
    sensors = config_entry.options.get(CONF_SENSORS, [])
    stream_source = config_entry.options.get(CONF_STREAM_SOURCE, DEFAULT_STREAM_SOURCE)
    control_light = config_entry.options.get(CONF_CONTROL_LIGHT, True)
    events = config_entry.options.get(CONF_EVENTS)

    # currently aiohttp only works with basic authentication
    # only valid for mjpeg streaming
    if (
        config_entry.options.get(CONF_AUTHENTICATION, DEFAULT_AUTHENTICATION)
        == HTTP_BASIC_AUTHENTICATION
    ):
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

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, CAMERA)
    )

    event_codes = dict()
    event_codes["binary_sensors"] = []
    event_codes["events"] = []

    if binary_sensors:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, BINARY_SENSOR)
        )

        event_codes["binary_sensors"] = [
            BINARY_SENSORS[sensor_type][SENSOR_EVENT_CODE]
            for sensor_type in binary_sensors
            if sensor_type not in BINARY_POLLED_SENSORS
        ]

    if events:
        event_codes["events"] = [event.strip() for event in events.split(",")]

    if event_codes["binary_sensors"] or event_codes["events"]:
        _start_event_monitor(hass, name, api, event_codes)

    if sensors:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, SENSOR)
        )

    if not hass.data[DATA_AMCREST][DEVICES]:
        return False

    await hass.async_add_executor_job(setup_amcrest_services, hass)

    return True


def setup_amcrest_services(hass):
    """Amcrest services."""

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
