"""The profiler integration."""
import asyncio
from contextlib import suppress
from datetime import timedelta
from functools import _lru_cache_wrapper
import logging
import reprlib
import sys
import threading
import time
import traceback
from typing import Any, cast

from lru import LRU  # pylint: disable=no-name-in-module
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_TYPE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN

SERVICE_START = "start"
SERVICE_MEMORY = "memory"
SERVICE_START_LOG_OBJECTS = "start_log_objects"
SERVICE_STOP_LOG_OBJECTS = "stop_log_objects"
SERVICE_START_LOG_OBJECT_SOURCES = "start_log_object_sources"
SERVICE_STOP_LOG_OBJECT_SOURCES = "stop_log_object_sources"
SERVICE_DUMP_LOG_OBJECTS = "dump_log_objects"
SERVICE_LRU_STATS = "lru_stats"
SERVICE_LOG_THREAD_FRAMES = "log_thread_frames"
SERVICE_LOG_EVENT_LOOP_SCHEDULED = "log_event_loop_scheduled"

_LRU_CACHE_WRAPPER_OBJECT = _lru_cache_wrapper.__name__
_SQLALCHEMY_LRU_OBJECT = "LRUCache"

_KNOWN_LRU_CLASSES = (
    "EventDataManager",
    "EventTypeManager",
    "StatesMetaManager",
    "StateAttributesManager",
    "StatisticsMetaManager",
    "IntegrationMatcher",
)

SERVICES = (
    SERVICE_START,
    SERVICE_MEMORY,
    SERVICE_START_LOG_OBJECTS,
    SERVICE_STOP_LOG_OBJECTS,
    SERVICE_DUMP_LOG_OBJECTS,
    SERVICE_LRU_STATS,
    SERVICE_LOG_THREAD_FRAMES,
    SERVICE_LOG_EVENT_LOOP_SCHEDULED,
)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

DEFAULT_MAX_OBJECTS = 5

CONF_SECONDS = "seconds"
CONF_MAX_OBJECTS = "max_objects"

LOG_INTERVAL_SUB = "log_interval_subscription"


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(  # noqa: C901
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up Profiler from a config entry."""
    lock = asyncio.Lock()
    domain_data = hass.data[DOMAIN] = {}

    async def _async_run_profile(call: ServiceCall) -> None:
        async with lock:
            await _async_generate_profile(hass, call)

    async def _async_run_memory_profile(call: ServiceCall) -> None:
        async with lock:
            await _async_generate_memory_profile(hass, call)

    async def _async_start_log_objects(call: ServiceCall) -> None:
        if LOG_INTERVAL_SUB in domain_data:
            raise HomeAssistantError("Object logging already started")

        persistent_notification.async_create(
            hass,
            (
                "Object growth logging has started. See [the logs](/config/logs) to"
                " track the growth of new objects."
            ),
            title="Object growth logging started",
            notification_id="profile_object_logging",
        )
        await hass.async_add_executor_job(_log_objects)
        domain_data[LOG_INTERVAL_SUB] = async_track_time_interval(
            hass, _log_objects, call.data[CONF_SCAN_INTERVAL]
        )

    async def _async_stop_log_objects(call: ServiceCall) -> None:
        if LOG_INTERVAL_SUB not in domain_data:
            raise HomeAssistantError("Object logging not running")

        persistent_notification.async_dismiss(hass, "profile_object_logging")
        domain_data.pop(LOG_INTERVAL_SUB)()

    async def _async_start_object_sources(call: ServiceCall) -> None:
        if LOG_INTERVAL_SUB in domain_data:
            raise HomeAssistantError("Object logging already started")

        persistent_notification.async_create(
            hass,
            (
                "Object source logging has started. See [the logs](/config/logs) to"
                " track the growth of new objects."
            ),
            title="Object source logging started",
            notification_id="profile_object_source_logging",
        )

        last_ids: set[int] = set()
        last_stats: dict[str, int] = {}

        async def _log_object_sources_with_max(*_: Any) -> None:
            await hass.async_add_executor_job(
                _log_object_sources, call.data[CONF_MAX_OBJECTS], last_ids, last_stats
            )

        await _log_object_sources_with_max()
        cancel_track = async_track_time_interval(
            hass, _log_object_sources_with_max, call.data[CONF_SCAN_INTERVAL]
        )

        @callback
        def _cancel():
            cancel_track()
            last_ids.clear()
            last_stats.clear()

        domain_data[LOG_INTERVAL_SUB] = _cancel

    @callback
    def _async_stop_object_sources(call: ServiceCall) -> None:
        if LOG_INTERVAL_SUB not in domain_data:
            raise HomeAssistantError("Object logging not running")

        persistent_notification.async_dismiss(hass, "profile_object_source_logging")
        domain_data.pop(LOG_INTERVAL_SUB)()

    def _dump_log_objects(call: ServiceCall) -> None:
        # Imports deferred to avoid loading modules
        # in memory since usually only one part of this
        # integration is used at a time
        import objgraph  # pylint: disable=import-outside-toplevel

        obj_type = call.data[CONF_TYPE]

        for obj in objgraph.by_type(obj_type):
            _LOGGER.critical(
                "%s object in memory: %s",
                obj_type,
                _safe_repr(obj),
            )

        persistent_notification.create(
            hass,
            (
                f"Objects with type {obj_type} have been dumped to the log. See [the"
                " logs](/config/logs) to review the repr of the objects."
            ),
            title="Object dump completed",
            notification_id="profile_object_dump",
        )

    def _lru_stats(call: ServiceCall) -> None:
        """Log the stats of all lru caches."""
        # Imports deferred to avoid loading modules
        # in memory since usually only one part of this
        # integration is used at a time
        import objgraph  # pylint: disable=import-outside-toplevel

        for lru in objgraph.by_type(_LRU_CACHE_WRAPPER_OBJECT):
            lru = cast(_lru_cache_wrapper, lru)
            _LOGGER.critical(
                "Cache stats for lru_cache %s at %s: %s",
                lru.__wrapped__,
                _get_function_absfile(lru.__wrapped__) or "unknown",
                lru.cache_info(),
            )

        for _class in _KNOWN_LRU_CLASSES:
            for class_with_lru_attr in objgraph.by_type(_class):
                for maybe_lru in class_with_lru_attr.__dict__.values():
                    if isinstance(maybe_lru, LRU):
                        _LOGGER.critical(
                            "Cache stats for LRU %s at %s: %s",
                            type(class_with_lru_attr),
                            _get_function_absfile(class_with_lru_attr) or "unknown",
                            maybe_lru.get_stats(),
                        )

        for lru in objgraph.by_type(_SQLALCHEMY_LRU_OBJECT):
            if (data := getattr(lru, "_data", None)) and isinstance(data, dict):
                for key, value in dict(data).items():
                    _LOGGER.critical(
                        "Cache data for sqlalchemy LRUCache %s: %s: %s", lru, key, value
                    )

        persistent_notification.create(
            hass,
            (
                "LRU cache states have been dumped to the log. See [the"
                " logs](/config/logs) to review the stats."
            ),
            title="LRU stats completed",
            notification_id="profile_lru_stats",
        )

    async def _async_dump_thread_frames(call: ServiceCall) -> None:
        """Log all thread frames."""
        frames = sys._current_frames()  # pylint: disable=protected-access
        main_thread = threading.main_thread()
        for thread in threading.enumerate():
            if thread == main_thread:
                continue
            ident = cast(int, thread.ident)
            _LOGGER.critical(
                "Thread [%s]: %s",
                thread.name,
                "".join(traceback.format_stack(frames.get(ident))).strip(),
            )

    async def _async_dump_scheduled(call: ServiceCall) -> None:
        """Log all scheduled in the event loop."""
        arepr = reprlib.aRepr
        original_maxstring = arepr.maxstring
        original_maxother = arepr.maxother
        arepr.maxstring = 300
        arepr.maxother = 300
        handle: asyncio.Handle
        try:
            for handle in getattr(hass.loop, "_scheduled"):
                if not handle.cancelled():
                    _LOGGER.critical("Scheduled: %s", handle)
        finally:
            arepr.maxstring = original_maxstring
            arepr.maxother = original_maxother

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_START,
        _async_run_profile,
        schema=vol.Schema(
            {vol.Optional(CONF_SECONDS, default=60.0): vol.Coerce(float)}
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_MEMORY,
        _async_run_memory_profile,
        schema=vol.Schema(
            {vol.Optional(CONF_SECONDS, default=60.0): vol.Coerce(float)}
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_START_LOG_OBJECTS,
        _async_start_log_objects,
        schema=vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period
            }
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_STOP_LOG_OBJECTS,
        _async_stop_log_objects,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_START_LOG_OBJECT_SOURCES,
        _async_start_object_sources,
        schema=vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): cv.time_period,
                vol.Optional(CONF_MAX_OBJECTS, default=DEFAULT_MAX_OBJECTS): vol.Range(
                    min=1, max=1024
                ),
            }
        ),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_STOP_LOG_OBJECT_SOURCES,
        _async_stop_object_sources,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_DUMP_LOG_OBJECTS,
        _dump_log_objects,
        schema=vol.Schema({vol.Required(CONF_TYPE): str}),
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LRU_STATS,
        _lru_stats,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LOG_THREAD_FRAMES,
        _async_dump_thread_frames,
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_LOG_EVENT_LOOP_SCHEDULED,
        _async_dump_scheduled,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    for service in SERVICES:
        hass.services.async_remove(domain=DOMAIN, service=service)
    if LOG_INTERVAL_SUB in hass.data[DOMAIN]:
        hass.data[DOMAIN][LOG_INTERVAL_SUB]()
    hass.data.pop(DOMAIN)
    return True


async def _async_generate_profile(hass: HomeAssistant, call: ServiceCall):
    # Imports deferred to avoid loading modules
    # in memory since usually only one part of this
    # integration is used at a time
    import cProfile  # pylint: disable=import-outside-toplevel

    start_time = int(time.time() * 1000000)
    persistent_notification.async_create(
        hass,
        (
            "The profile has started. This notification will be updated when it is"
            " complete."
        ),
        title="Profile Started",
        notification_id=f"profiler_{start_time}",
    )
    profiler = cProfile.Profile()
    profiler.enable()
    await asyncio.sleep(float(call.data[CONF_SECONDS]))
    profiler.disable()

    cprofile_path = hass.config.path(f"profile.{start_time}.cprof")
    callgrind_path = hass.config.path(f"callgrind.out.{start_time}")
    await hass.async_add_executor_job(
        _write_profile, profiler, cprofile_path, callgrind_path
    )
    persistent_notification.async_create(
        hass,
        (
            f"Wrote cProfile data to {cprofile_path} and callgrind data to"
            f" {callgrind_path}"
        ),
        title="Profile Complete",
        notification_id=f"profiler_{start_time}",
    )


async def _async_generate_memory_profile(hass: HomeAssistant, call: ServiceCall):
    # Imports deferred to avoid loading modules
    # in memory since usually only one part of this
    # integration is used at a time
    from guppy import hpy  # pylint: disable=import-outside-toplevel

    start_time = int(time.time() * 1000000)
    persistent_notification.async_create(
        hass,
        (
            "The memory profile has started. This notification will be updated when it"
            " is complete."
        ),
        title="Profile Started",
        notification_id=f"memory_profiler_{start_time}",
    )
    heap_profiler = hpy()
    heap_profiler.setref()
    await asyncio.sleep(float(call.data[CONF_SECONDS]))
    heap = heap_profiler.heap()

    heap_path = hass.config.path(f"heap_profile.{start_time}.hpy")
    await hass.async_add_executor_job(_write_memory_profile, heap, heap_path)
    persistent_notification.async_create(
        hass,
        f"Wrote heapy memory profile to {heap_path}",
        title="Profile Complete",
        notification_id=f"memory_profiler_{start_time}",
    )


def _write_profile(profiler, cprofile_path, callgrind_path):
    # Imports deferred to avoid loading modules
    # in memory since usually only one part of this
    # integration is used at a time
    from pyprof2calltree import convert  # pylint: disable=import-outside-toplevel

    profiler.create_stats()
    profiler.dump_stats(cprofile_path)
    convert(profiler.getstats(), callgrind_path)


def _write_memory_profile(heap, heap_path):
    heap.byrcs.dump(heap_path)


def _log_objects(*_):
    # Imports deferred to avoid loading modules
    # in memory since usually only one part of this
    # integration is used at a time
    import objgraph  # pylint: disable=import-outside-toplevel

    _LOGGER.critical("Memory Growth: %s", objgraph.growth(limit=1000))


def _get_function_absfile(func: Any) -> str | None:
    """Get the absolute file path of a function."""
    import inspect  # pylint: disable=import-outside-toplevel

    abs_file: str | None = None
    with suppress(Exception):
        abs_file = inspect.getabsfile(func)
    return abs_file


def _safe_repr(obj: Any) -> str:
    """Get the repr of an object but keep going if there is an exception.

    We wrap repr to ensure if one object cannot be serialized, we can
    still get the rest.
    """
    try:
        return repr(obj)
    except Exception:  # pylint: disable=broad-except
        return f"Failed to serialize {type(obj)}"


def _find_backrefs_not_to_self(_object: Any) -> list[str]:
    import objgraph  # pylint: disable=import-outside-toplevel

    return [
        _safe_repr(backref)
        for backref in objgraph.find_backref_chain(
            _object, lambda obj: obj is not _object
        )
    ]


def _log_object_sources(
    max_objects: int, last_ids: set[int], last_stats: dict[str, int]
) -> None:
    # Imports deferred to avoid loading modules
    # in memory since usually only one part of this
    # integration is used at a time
    import gc  # pylint: disable=import-outside-toplevel

    gc.collect()

    objects = gc.get_objects()
    new_objects: list[object] = []
    new_objects_overflow: dict[str, int] = {}
    current_ids = set()
    new_stats: dict[str, int] = {}
    had_new_object_growth = False
    try:
        for _object in objects:
            object_type = type(_object).__name__
            new_stats[object_type] = new_stats.get(object_type, 0) + 1

        for _object in objects:
            id_ = id(_object)
            current_ids.add(id_)
            if id_ in last_ids:
                continue
            object_type = type(_object).__name__
            if last_stats.get(object_type, 0) < new_stats[object_type]:
                if len(new_objects) < max_objects:
                    new_objects.append(_object)
                else:
                    new_objects_overflow.setdefault(object_type, 0)
                    new_objects_overflow[object_type] += 1

        for _object in new_objects:
            had_new_object_growth = True
            object_type = type(_object).__name__
            _LOGGER.critical(
                "New object %s (%s/%s) at %s: %s",
                object_type,
                last_stats.get(object_type, 0),
                new_stats[object_type],
                _get_function_absfile(_object) or _find_backrefs_not_to_self(_object),
                _safe_repr(_object),
            )

        for object_type, count in last_stats.items():
            new_stats[object_type] = max(new_stats.get(object_type, 0), count)
    finally:
        # Break reference cycles
        del objects
        del new_objects
        last_ids.clear()
        last_ids.update(current_ids)
        last_stats.clear()
        last_stats.update(new_stats)
        del new_stats
        del current_ids

    if new_objects_overflow:
        _LOGGER.critical("New objects overflowed by %s", new_objects_overflow)
    elif not had_new_object_growth:
        _LOGGER.critical("No new object growth found")
