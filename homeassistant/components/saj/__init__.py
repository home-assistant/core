"""The saj component."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import pysaj

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_start

from .const import CONNECTION_TYPES

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

MIN_INTERVAL_SEC = 5
MAX_INTERVAL_SEC = 300


@callback
def async_track_time_interval_backoff(
    hass: HomeAssistant, action: Callable[[], Coroutine[Any, Any, bool]]
) -> CALLBACK_TYPE:
    """Fire `action` on an interval; double the interval (capped) when it returns False."""
    remove: CALLBACK_TYPE | None = None
    interval = MIN_INTERVAL_SEC

    async def interval_listener(_now: datetime | None = None) -> None:
        nonlocal interval, remove
        try:
            if await action():
                interval = MIN_INTERVAL_SEC
            else:
                interval = min(interval * 2, MAX_INTERVAL_SEC)
        finally:
            remove = async_call_later(hass, interval, interval_listener)

    hass.async_create_task(interval_listener())

    def remove_listener() -> None:
        if remove:
            remove()

    return remove_listener


class SAJPolling:
    """Interval polling with backoff; entities register for per-poll callbacks."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        saj: pysaj.SAJ,
        sensor_def: pysaj.Sensors,
    ) -> None:
        """Initialize polling for one config entry."""
        self._hass = hass
        self._entry = entry
        self._saj = saj
        self._sensor_def = sensor_def
        self._listeners: list[Callable[[bool], None]] = []
        self._remove_backoff: CALLBACK_TYPE | None = None
        self._cancel_at_start: CALLBACK_TYPE | None = None
        self._unsub_stop: CALLBACK_TYPE | None = None

    @callback
    def async_add_poll_listener(
        self, target: Callable[[bool], None]
    ) -> Callable[[], None]:
        """Register to be called after each poll with the read success flag."""

        @callback
        def remove_listener() -> None:
            self._listeners.remove(target)
            if not self._listeners:
                self._async_stop_backoff()
                if self._cancel_at_start:
                    self._cancel_at_start()
                    self._cancel_at_start = None

        self._listeners.append(target)
        if len(self._listeners) == 1:
            self._schedule_polling_start()
        return remove_listener

    def _schedule_polling_start(self) -> None:
        @callback
        def start(_hass: HomeAssistant) -> None:
            self._cancel_at_start = None
            if not self._listeners:
                return
            self._async_start_backoff()

        self._cancel_at_start = async_at_start(self._hass, start)

    @callback
    def _async_start_backoff(self) -> None:
        self._remove_backoff = async_track_time_interval_backoff(
            self._hass, self._async_poll_with_notify
        )

        @callback
        def stop_on_hass_stop(_event: Event) -> None:
            self._async_stop_backoff()

        self._unsub_stop = self._hass.bus.async_listen(
            EVENT_HOMEASSISTANT_STOP, stop_on_hass_stop
        )

    async def _async_poll_with_notify(self) -> bool:
        try:
            success = await self._saj.read(self._sensor_def)
        except pysaj.UnauthorizedException:
            _LOGGER.error(
                "Username and/or password rejected during polling for %s",
                self._entry.title,
            )
            success = False
        except pysaj.UnexpectedResponseException as err:
            _LOGGER.error(
                "Error in SAJ, please check host/ip address. Original error: %s", err
            )
            success = False
        except (TimeoutError, OSError) as err:
            _LOGGER.error("Error communicating with SAJ: %s", err)
            success = False

        for listener in list(self._listeners):
            listener(success)
        return success

    @callback
    def _async_stop_backoff(self) -> None:
        if self._remove_backoff:
            self._remove_backoff()
            self._remove_backoff = None
        if self._unsub_stop:
            self._unsub_stop()
            self._unsub_stop = None

    @callback
    def async_shutdown(self) -> None:
        """Cancel polling and any deferred start."""
        self._listeners.clear()
        self._async_stop_backoff()
        if self._cancel_at_start:
            self._cancel_at_start()
            self._cancel_at_start = None


@dataclass(frozen=True, slots=True)
class SAJRuntimeData:
    """Runtime data attached to a SAJ config entry."""

    saj: pysaj.SAJ
    sensor_def: pysaj.Sensors
    polling: SAJPolling


type SAJConfigEntry = ConfigEntry[SAJRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Set up SAJ from a config entry."""
    host = entry.data[CONF_HOST]
    connection_type = entry.data[CONF_TYPE]
    username = entry.data.get(CONF_USERNAME, None)
    password = entry.data.get(CONF_PASSWORD, None)

    # Create SAJ connection
    kwargs: dict[str, Any] = {}
    wifi = connection_type == CONNECTION_TYPES[1]
    if wifi:
        kwargs["wifi"] = True
        if username:
            kwargs["username"] = username
        if password:
            kwargs["password"] = password

    async def _async_connect() -> tuple[pysaj.SAJ, pysaj.Sensors]:
        """Connect to SAJ and verify connection."""
        saj = pysaj.SAJ(host, **kwargs)
        sensor_def = pysaj.Sensors(wifi)
        done = await saj.read(sensor_def)
        if not done:
            raise ConfigEntryNotReady("Failed to read initial sensor data")
        return saj, sensor_def

    try:
        saj, sensor_def = await _async_connect()
    except pysaj.UnauthorizedException as err:
        raise ConfigEntryNotReady("Authentication failed") from err
    except pysaj.UnexpectedResponseException as err:
        raise ConfigEntryNotReady(f"Connection error: {err}") from err
    except TimeoutError as err:
        raise ConfigEntryNotReady(f"Connection timeout: {err}") from err
    except OSError as err:
        raise ConfigEntryNotReady(f"Network error: {err}") from err

    polling = SAJPolling(hass, entry, saj, sensor_def)
    entry.runtime_data = SAJRuntimeData(saj=saj, sensor_def=sensor_def, polling=polling)
    entry.async_on_unload(polling.async_shutdown)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SAJConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
