"""Support for Amcrest IP cameras."""

import asyncio
from collections.abc import AsyncGenerator, Callable
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

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
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
    HTTP_BASIC_AUTHENTICATION,
    Platform,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send, dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.typing import ConfigType

from .binary_sensor import (
    BINARY_SENSOR_KEYS,
    BINARY_SENSORS,
    check_binary_sensors,
    get_default_binary_sensor_descriptions,
)
from .camera import STREAM_SOURCE_LIST
from .const import (
    COMM_RETRIES,
    COMM_TIMEOUT,
    DOMAIN,
    RESOLUTION_LIST,
    SERVICE_EVENT,
    SERVICE_UPDATE,
)
from .entry_options import get_binary_sensor_keys
from .helpers import service_signal
from .sensor import SENSOR_KEYS
from .services import async_setup_services
from .switch import SWITCH_KEYS

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.SWITCH,
)

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

SCAN_INTERVAL = timedelta(seconds=10)

AUTHENTICATION_LIST = {"basic": "basic"}

INTEGRATION_TITLE = "Amcrest"
DEPRECATED_YAML_BREAKS_IN = "2026.9.0"


def _has_unique_names(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
            cv.ensure_list,
            [vol.In(BINARY_SENSOR_KEYS)],
            vol.Unique(),
            check_binary_sensors,
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
    {DOMAIN: vol.All(cv.ensure_list, [AMCREST_SCHEMA], _has_unique_names)},
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

    @callback
    def _async_start_recovery(self) -> None:
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
            return await super().async_command(*args, **kwargs)

    @asynccontextmanager
    async def async_stream_command(
        self, *args: Any, **kwargs: Any
    ) -> AsyncGenerator[httpx.Response]:
        """amcrest.ApiWrapper.command wrapper to catch errors."""
        async with (
            self._async_command_wrapper(),
            super().async_stream_command(*args, **kwargs) as ret,
        ):
            yield ret

    @asynccontextmanager
    async def _async_command_wrapper(self) -> AsyncGenerator[None]:
        try:
            yield
        except LoginError as ex:
            async with self._async_wrap_lock:
                self._async_handle_offline(ex)
            raise
        except AmcrestError:
            async with self._async_wrap_lock:
                self._async_handle_error()
            raise
        async with self._async_wrap_lock:
            self._async_set_online()

    def _handle_offline_thread_safe(self, ex: Exception) -> bool:
        """Handle camera offline status shared between threads and event loop.

        Returns if the camera was online as a bool.
        """
        with self._wrap_lock:
            was_online = self.available
            was_login_err = self._wrap_login_err
            self._wrap_login_err = True
        if not was_login_err:
            _LOGGER.error("%s camera offline: Login error: %s", self._wrap_name, ex)
        return was_online

    def _handle_offline(self, ex: Exception) -> None:
        """Handle camera offline status from a thread."""
        if self._handle_offline_thread_safe(ex):
            self._hass.loop.call_soon_threadsafe(self._async_start_recovery)

    @callback
    def _async_handle_offline(self, ex: Exception) -> None:
        if self._handle_offline_thread_safe(ex):
            self._async_start_recovery()

    def _handle_error_thread_safe(self) -> bool:
        """Handle camera error status shared between threads and event loop.

        Returns if the camera was online and is now offline as
        a bool.
        """
        with self._wrap_lock:
            was_online = self.available
            errs = self._wrap_errors = self._wrap_errors + 1
            offline = not self.available
        _LOGGER.debug("%s camera errs: %i", self._wrap_name, errs)
        return was_online and offline

    def _handle_error(self) -> None:
        """Handle camera error status from a thread."""
        if self._handle_error_thread_safe():
            _LOGGER.error("%s camera offline: Too many errors", self._wrap_name)
            self._hass.loop.call_soon_threadsafe(self._async_start_recovery)

    @callback
    def _async_handle_error(self) -> None:
        """Handle camera error status from the event loop."""
        if self._handle_error_thread_safe():
            _LOGGER.error("%s camera offline: Too many errors", self._wrap_name)
            self._async_start_recovery()

    def _set_online_thread_safe(self) -> bool:
        """Set camera online status shared between threads and event loop.

        Returns if the camera was offline as a bool.
        """
        with self._wrap_lock:
            was_offline = not self.available
            self._wrap_errors = 0
            self._wrap_login_err = False
        return was_offline

    def _set_online(self) -> None:
        """Set camera online status from a thread."""
        if self._set_online_thread_safe():
            self._hass.loop.call_soon_threadsafe(self._async_signal_online)

    @callback
    def _async_set_online(self) -> None:
        """Set camera online status from the event loop."""
        if self._set_online_thread_safe():
            self._async_signal_online()

    @callback
    def _async_signal_online(self) -> None:
        """Signal that camera is back online."""
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
    stop_event: threading.Event | None = None,
) -> None:
    """Monitor camera events. Exits when stop_event is set (config flow only)."""
    while stop_event is None or not stop_event.is_set():
        if stop_event:
            api.available_flag.wait(timeout=1.0)
        else:
            api.available_flag.wait()
        if stop_event and stop_event.is_set():
            break
        try:
            for code, payload in api.event_actions("All"):
                if stop_event and stop_event.is_set():
                    return
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
    stop_event: threading.Event | None = None,
) -> threading.Event | None:
    """Start event monitor. Returns stop_event when provided (for config flow)."""
    thread = threading.Thread(
        target=_monitor_events,
        name=f"Amcrest {name}",
        args=(hass, name, api, event_codes, stop_event),
        daemon=stop_event is None,
    )
    thread.start()
    return stop_event


@dataclass
class AmcrestDevice:
    """Representation of a base Amcrest discovery device."""

    api: AmcrestChecker
    authentication: aiohttp.BasicAuth | None
    ffmpeg_arguments: str
    stream_source: str
    resolution: int
    control_light: bool
    channel: int = 0
    name: str = ""


@dataclass
class AmcrestRuntimeData:
    """Runtime data stored on the config entry."""

    device: AmcrestDevice
    stop_event: threading.Event | None = None


type AmcrestConfigEntry = ConfigEntry[AmcrestRuntimeData]


def _get_entry_binary_sensor_keys(entry: AmcrestConfigEntry) -> list[str]:
    """Return binary sensor keys configured for a config entry."""
    if (keys := get_binary_sensor_keys(entry)) is not None:
        return keys

    return [description.key for description in get_default_binary_sensor_descriptions()]


def _event_codes_for_binary_sensor_keys(binary_keys: list[str]) -> set[str]:
    """Return event codes monitored for the given binary sensor keys."""
    binary_key_set = set(binary_keys)
    return {
        event_code
        for sensor in BINARY_SENSORS
        if sensor.key in binary_key_set
        and not sensor.should_poll
        and sensor.event_codes is not None
        for event_code in sensor.event_codes
    }


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Import Amcrest YAML configuration and set up services."""
    if DOMAIN in config:
        hass.async_create_task(_async_import_yaml(hass, config))

    async_setup_services(hass)
    return True


async def _async_import_yaml(hass: HomeAssistant, config: ConfigType) -> None:
    """Import YAML camera configurations into config entries."""
    deprecated_issue_created = False

    for entry_config in config[DOMAIN]:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=entry_config,
        )
        if result.get("type") is FlowResultType.ABORT:
            reason = result.get("reason")
            if reason != "already_configured":
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    (
                        "deprecated_yaml_import_issue_"
                        f"{entry_config[CONF_HOST]}_{entry_config[CONF_PORT]}_{reason}"
                    ),
                    breaks_in_ha_version=DEPRECATED_YAML_BREAKS_IN,
                    is_fixable=False,
                    issue_domain=DOMAIN,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=f"deprecated_yaml_import_issue_{reason}",
                    translation_placeholders={
                        "domain": DOMAIN,
                        "integration_title": INTEGRATION_TITLE,
                    },
                )
            continue

        if not deprecated_issue_created:
            ir.async_create_issue(
                hass,
                HOMEASSISTANT_DOMAIN,
                f"deprecated_yaml_{DOMAIN}",
                breaks_in_ha_version=DEPRECATED_YAML_BREAKS_IN,
                is_fixable=False,
                issue_domain=DOMAIN,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_yaml",
                translation_placeholders={
                    "domain": DOMAIN,
                    "integration_title": INTEGRATION_TITLE,
                },
            )
            deprecated_issue_created = True


async def async_setup_entry(hass: HomeAssistant, entry: AmcrestConfigEntry) -> bool:
    """Set up Amcrest from a config entry."""
    config_data = dict(entry.data)
    config_data.update(entry.options)

    config_data.setdefault(CONF_AUTHENTICATION, HTTP_BASIC_AUTHENTICATION)
    config_data.setdefault(CONF_RESOLUTION, DEFAULT_RESOLUTION)
    config_data.setdefault(CONF_STREAM_SOURCE, STREAM_SOURCE_LIST[0])
    config_data.setdefault(CONF_FFMPEG_ARGUMENTS, DEFAULT_ARGUMENTS)
    config_data.setdefault(CONF_CONTROL_LIGHT, True)

    name: str = entry.title
    username: str = config_data[CONF_USERNAME]
    password: str = config_data[CONF_PASSWORD]

    api = AmcrestChecker(
        hass, name, config_data[CONF_HOST], config_data[CONF_PORT], username, password
    )

    ffmpeg_arguments = config_data[CONF_FFMPEG_ARGUMENTS]
    resolution = RESOLUTION_LIST[config_data[CONF_RESOLUTION]]
    stream_source = config_data[CONF_STREAM_SOURCE]
    control_light = config_data.get(CONF_CONTROL_LIGHT, True)

    if config_data.get(CONF_AUTHENTICATION, HTTP_BASIC_AUTHENTICATION) == (
        HTTP_BASIC_AUTHENTICATION
    ):
        authentication: aiohttp.BasicAuth | None = aiohttp.BasicAuth(username, password)
    else:
        authentication = None

    device = AmcrestDevice(
        api,
        authentication,
        ffmpeg_arguments,
        stream_source,
        resolution,
        control_light,
    )
    device.name = name

    event_codes = _event_codes_for_binary_sensor_keys(
        _get_entry_binary_sensor_keys(entry)
    )

    runtime_data = AmcrestRuntimeData(device=device)
    entry.runtime_data = runtime_data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    runtime_data.stop_event = threading.Event()
    _start_event_monitor(hass, name, api, event_codes, runtime_data.stop_event)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AmcrestConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.runtime_data.stop_event is not None:
        entry.runtime_data.stop_event.set()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
