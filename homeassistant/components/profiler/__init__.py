"""The profiler integration."""
import asyncio
import cProfile
from datetime import timedelta
import logging
import time

import objgraph
from pyprof2calltree import convert
from sqlalchemy.orm.session import Session
import voluptuous as vol

from homeassistant.components.recorder.models import Events, States
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

SERVICE_START = "start"
CONF_SECONDS = "seconds"

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the profiler component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Profiler from a config entry."""

    lock = asyncio.Lock()

    async def _async_run_profile(call: ServiceCall):
        async with lock:
            await _async_generate_profile(hass, call)

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_START,
        _async_run_profile,
        schema=vol.Schema(
            {vol.Optional(CONF_SECONDS, default=60.0): vol.Coerce(float)}
        ),
    )

    @callback
    def _log_objects(*_):
        _LOGGER.debug("Most common types: %s", objgraph.most_common_types(limit=25))
        _LOGGER.debug("Growth: %s", objgraph.growth(limit=25))
        _LOGGER.debug(
            "Most States: %s",
            objgraph.most_common_types(filter=lambda x: isinstance(x, States)),
        )
        _LOGGER.debug(
            "Growth States: %s",
            objgraph.growth(filter=lambda x: isinstance(x, States)),
        )
        _LOGGER.debug(
            "Most Events: %s",
            objgraph.most_common_types(filter=lambda x: isinstance(x, Events)),
        )
        _LOGGER.debug(
            "Growth Events: %s",
            objgraph.growth(filter=lambda x: isinstance(x, Events)),
        )
        _LOGGER.debug(
            "Most Session: %s",
            objgraph.most_common_types(filter=lambda x: isinstance(x, Session)),
        )
        _LOGGER.debug(
            "Growth Session: %s",
            objgraph.growth(filter=lambda x: isinstance(x, Session)),
        )

    async_track_time_interval(hass, _log_objects, timedelta(seconds=30))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.services.async_remove(domain=DOMAIN, service=SERVICE_START)
    return True


async def _async_generate_profile(hass: HomeAssistant, call: ServiceCall):
    start_time = int(time.time() * 1000000)
    hass.components.persistent_notification.async_create(
        "The profile started. This notification will be updated when it is complete.",
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
    hass.components.persistent_notification.async_create(
        f"Wrote cProfile data to {cprofile_path} and callgrind data to {callgrind_path}",
        title="Profile Complete",
        notification_id=f"profiler_{start_time}",
    )


def _write_profile(profiler, cprofile_path, callgrind_path):
    profiler.create_stats()
    profiler.dump_stats(cprofile_path)
    convert(profiler.getstats(), callgrind_path)
