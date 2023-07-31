"""Support for Amcrest IP cameras."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import threading
from typing import Any

import aiohttp
from amcrest import AmcrestError, ApiWrapper, LoginError
import httpx
import voluptuous as vol

from homeassistant.auth.models import User
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.components.camera import DOMAIN as CAMERA
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
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
    CONF_SWITCHES,
    CONF_USERNAME,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    HTTP_BASIC_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    Unauthorized,
    UnknownUser,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.service import async_extract_entity_ids
from homeassistant.helpers.typing import ConfigType

from .binary_sensor import BINARY_SENSOR_KEYS, BINARY_SENSORS
from .camera import CAMERA_SERVICES
from .const import (
    AUTHENTICATION_LIST,
    CAMERAS,
    COMM_RETRIES,
    COMM_TIMEOUT,
    CONF_CONTROL_LIGHT,
    CONF_FFMPEG_ARGUMENTS,
    CONF_RESOLUTION,
    CONF_STREAM_SOURCE,
    DEFAULT_AUTHENTICATION,
    DEFAULT_CONTROL_LIGHT,
    DEFAULT_FFMPEG_ARGUMENTS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_RESOLUTION,
    DEFAULT_STREAM_SOURCE,
    DEVICES,
    DOMAIN,
    RESOLUTION_LIST,
    SERVICE_EVENT,
    SERVICE_UPDATE,
    STREAM_SOURCE_LIST,
)
from .helpers import service_signal
from .sensor import SENSOR_KEYS
from .switch import SWITCH_KEYS

_LOGGER = logging.getLogger(__name__)

MAX_ERRORS = 5
RECHECK_INTERVAL = timedelta(minutes=1)

NOTIFICATION_ID = "amcrest_notification"
NOTIFICATION_TITLE = "Amcrest Camera Setup"

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORMS = (BINARY_SENSOR, CAMERA, SENSOR)


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
        vol.Optional(
            CONF_FFMPEG_ARGUMENTS, default=DEFAULT_FFMPEG_ARGUMENTS
        ): cv.string,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_BINARY_SENSORS): vol.All(
            cv.ensure_list,
            [vol.In(BINARY_SENSOR_KEYS)],
            vol.Unique(),
        ),
        vol.Optional(CONF_SWITCHES): vol.All(
            cv.ensure_list, [vol.In(SWITCH_KEYS)], vol.Unique()
        ),
        vol.Optional(CONF_SENSORS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)], vol.Unique()
        ),
        vol.Optional(CONF_CONTROL_LIGHT, default=True): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [AMCREST_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


class AmcrestChecker(ApiWrapper):
    """amcrest.ApiWrapper wrapper for catching errors."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        host: str,
        port: int,
        user: str,
        password: str,
    ) -> None:
        """Initialize."""
        self._hass = hass
        self._wrap_name = name
        self._wrap_errors = 0
        self._wrap_lock = threading.Lock()
        self._async_wrap_lock = asyncio.Lock()
        self._wrap_login_err = False
        self._wrap_event_flag = threading.Event()
        self._wrap_event_flag.set()
        self._async_wrap_event_flag = asyncio.Event()
        self._async_wrap_event_flag.set()
        self._unsub_recheck: Callable[[], None] | None = None
        super().__init__(
            host,
            port,
            user,
            password,
            retries_connection=COMM_RETRIES,
            timeout_protocol=COMM_TIMEOUT,
        )

    @property
    def available(self) -> bool:
        """Return if camera's API is responding."""
        return self._wrap_errors <= MAX_ERRORS and not self._wrap_login_err

    @property
    def available_flag(self) -> threading.Event:
        """Return event flag that indicates if camera's API is responding."""
        return self._wrap_event_flag

    @property
    def async_available_flag(self) -> asyncio.Event:
        """Return event flag that indicates if camera's API is responding."""
        return self._async_wrap_event_flag

    def _start_recovery(self) -> None:
        self.available_flag.clear()
        self.async_available_flag.clear()
        async_dispatcher_send(
            self._hass, service_signal(SERVICE_UPDATE, self._wrap_name)
        )
        self._unsub_recheck = async_track_time_interval(
            self._hass, self._wrap_test_online, RECHECK_INTERVAL
        )

    def command(self, *args: Any, **kwargs: Any) -> Any:
        """amcrest.ApiWrapper.command wrapper to catch errors."""
        try:
            ret = super().command(*args, **kwargs)
        except LoginError as ex:
            self._handle_offline(ex)
            raise
        except AmcrestError:
            self._handle_error()
            raise
        self._set_online()
        return ret

    async def async_command(self, *args: Any, **kwargs: Any) -> httpx.Response:
        """amcrest.ApiWrapper.command wrapper to catch errors."""
        async with self._async_command_wrapper():
            ret = await super().async_command(*args, **kwargs)
        return ret

    @asynccontextmanager
    async def async_stream_command(
        self, *args: Any, **kwargs: Any
    ) -> AsyncIterator[httpx.Response]:
        """amcrest.ApiWrapper.command wrapper to catch errors."""
        async with self._async_command_wrapper(), super().async_stream_command(
            *args, **kwargs
        ) as ret:
            yield ret

    @asynccontextmanager
    async def _async_command_wrapper(self) -> AsyncIterator[None]:
        try:
            yield
        except LoginError as ex:
            async with self._async_wrap_lock:
                self._handle_offline(ex)
            raise
        except AmcrestError:
            async with self._async_wrap_lock:
                self._handle_error()
            raise
        async with self._async_wrap_lock:
            self._set_online()

    def _handle_offline(self, ex: Exception) -> None:
        with self._wrap_lock:
            was_online = self.available
            was_login_err = self._wrap_login_err
            self._wrap_login_err = True
        if not was_login_err:
            _LOGGER.error("%s camera offline: Login error: %s", self._wrap_name, ex)
        if was_online:
            self._start_recovery()

    def _handle_error(self) -> None:
        with self._wrap_lock:
            was_online = self.available
            errs = self._wrap_errors = self._wrap_errors + 1
            offline = not self.available
        _LOGGER.debug("%s camera errs: %i", self._wrap_name, errs)
        if was_online and offline:
            _LOGGER.error("%s camera offline: Too many errors", self._wrap_name)
            self._start_recovery()

    def _set_online(self) -> None:
        with self._wrap_lock:
            was_offline = not self.available
            self._wrap_errors = 0
            self._wrap_login_err = False
        if was_offline:
            assert self._unsub_recheck is not None
            self._unsub_recheck()
            self._unsub_recheck = None
            _LOGGER.error("%s camera back online", self._wrap_name)
            self.available_flag.set()
            self.async_available_flag.set()
            async_dispatcher_send(
                self._hass, service_signal(SERVICE_UPDATE, self._wrap_name)
            )

    async def _wrap_test_online(self, now: datetime) -> None:
        """Test if camera is back online."""
        _LOGGER.debug("Testing if %s back online", self._wrap_name)
        with suppress(AmcrestError):
            await self.async_current_time


def _monitor_events(
    hass: HomeAssistant,
    name: str,
    api: AmcrestChecker,
    event_codes: set[str],
) -> None:
    while True:
        api.available_flag.wait()
        try:
            for code, payload in api.event_actions("All"):
                event_data = {"camera": name, "event": code, "payload": payload}
                hass.bus.fire("amcrest", event_data)
                if code in event_codes:
                    signal = service_signal(SERVICE_EVENT, name, code)
                    start = any(
                        str(key).lower() == "action" and str(val).lower() == "start"
                        for key, val in payload.items()
                    )
                    _LOGGER.debug("Sending signal: '%s': %s", signal, start)
                    dispatcher_send(hass, signal, start)
        except AmcrestError as error:
            _LOGGER.warning(
                "Error while processing events from %s camera: %r", name, error
            )


def _start_event_monitor(
    hass: HomeAssistant,
    name: str,
    api: AmcrestChecker,
    event_codes: set[str],
) -> None:
    thread = threading.Thread(
        target=_monitor_events,
        name=f"Amcrest {name}",
        args=(hass, name, api, event_codes),
        daemon=True,
    )
    thread.start()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    name = entry.data[CONF_NAME]
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    api = AmcrestChecker(
        hass,
        name=name,
        host=host,
        port=port,
        user=username,
        password=password,
    )

    try:
        serial_number = await api.async_serial_number
    except LoginError as err:
        raise ConfigEntryAuthFailed(f"Invalid authentication for {name}") from err
    except AmcrestError as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to {name} at {host}:{port}"
        ) from err

    if (
        entry.options.get(CONF_AUTHENTICATION, DEFAULT_AUTHENTICATION)
        == HTTP_BASIC_AUTHENTICATION
    ):
        authentication: aiohttp.BasicAuth | None = aiohttp.BasicAuth(username, password)
    else:
        authentication = None

    ffmpeg_arguments: str = entry.options.get(
        CONF_FFMPEG_ARGUMENTS, DEFAULT_FFMPEG_ARGUMENTS
    )
    stream_source: str = entry.options.get(CONF_STREAM_SOURCE, DEFAULT_STREAM_SOURCE)
    resolution: str = entry.options.get(CONF_RESOLUTION, DEFAULT_RESOLUTION)
    control_light: bool = entry.options.get(CONF_CONTROL_LIGHT, DEFAULT_CONTROL_LIGHT)

    hass.data.setdefault(DOMAIN, {DEVICES: {}, CAMERAS: []})
    hass.data[DOMAIN][DEVICES][entry.entry_id] = AmcrestDevice(
        api,
        serial_number,
        authentication,
        ffmpeg_arguments,
        stream_source,
        resolution,
        control_light,
    )

    event_codes = set()
    binary_sensors = entry.options.get(CONF_BINARY_SENSORS, [])
    if binary_sensors:
        event_codes = {
            event_code
            for sensor in BINARY_SENSORS
            if sensor.key in binary_sensors
            and not sensor.should_poll
            and sensor.event_codes is not None
            for event_code in sensor.event_codes
        }

    _start_event_monitor(hass, name, api, event_codes)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    def have_permission(user: User | None, entity_id: str) -> bool:
        return not user or user.permissions.check_entity(entity_id, POLICY_CONTROL)

    async def async_extract_from_service(call: ServiceCall) -> list[str]:
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
                for entity_id in hass.data[DOMAIN][CAMERAS]
                if have_permission(user, entity_id)
            ]

        if call.data.get(ATTR_ENTITY_ID) == ENTITY_MATCH_NONE:
            return []

        call_ids = await async_extract_entity_ids(hass, call)
        entity_ids = []
        for entity_id in hass.data[DOMAIN][CAMERAS]:
            if entity_id not in call_ids:
                continue
            if not have_permission(user, entity_id):
                raise Unauthorized(
                    context=call.context, entity_id=entity_id, permission=POLICY_CONTROL
                )
            entity_ids.append(entity_id)
        return entity_ids

    async def async_service_handler(call: ServiceCall) -> None:
        args = []
        for arg in CAMERA_SERVICES[call.service][2]:
            args.append(call.data[arg])
        for entity_id in await async_extract_from_service(call):
            async_dispatcher_send(hass, service_signal(call.service, entity_id), *args)

    for service, params in CAMERA_SERVICES.items():
        if not hass.services.has_service(DOMAIN, service):
            hass.services.async_register(
                DOMAIN, service, async_service_handler, params[0]
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Amcrest config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][DEVICES][entry.entry_id]
        if len(hass.data[DOMAIN][DEVICES]) == 0:
            del hass.data[DOMAIN]
            for service in CAMERA_SERVICES:
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Amcrest IP Camera component."""
    if DOMAIN not in config:
        return True

    for device in config[DOMAIN]:
        new_config = {
            CONF_NAME: device[CONF_NAME],
            CONF_HOST: device[CONF_HOST],
            CONF_PORT: device[CONF_PORT],
            CONF_USERNAME: device[CONF_USERNAME],
            CONF_PASSWORD: device[CONF_PASSWORD],
            CONF_FFMPEG_ARGUMENTS: device[CONF_FFMPEG_ARGUMENTS],
            CONF_RESOLUTION: device[CONF_RESOLUTION],
            CONF_STREAM_SOURCE: device[CONF_STREAM_SOURCE],
            CONF_AUTHENTICATION: device[CONF_AUTHENTICATION],
            CONF_BINARY_SENSORS: device.get(CONF_BINARY_SENSORS, []),
            CONF_SENSORS: device.get(CONF_SENSORS, []),
            CONF_SWITCHES: device.get(CONF_SWITCHES, []),
            CONF_CONTROL_LIGHT: device[CONF_CONTROL_LIGHT],
        }

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=new_config
            )
        )

        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml",
            breaks_in_ha_version=None,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
        )

    return True


@dataclass
class AmcrestDevice:
    """Representation of a base Amcrest discovery device."""

    api: AmcrestChecker
    serial_number: str
    authentication: aiohttp.BasicAuth | None
    ffmpeg_arguments: str | list[str]
    stream_source: str
    resolution: str
    control_light: bool
    channel: int = 0
