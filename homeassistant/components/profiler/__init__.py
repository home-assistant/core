"""The profiler integration."""
import asyncio
import cProfile
import time

from pyprof2calltree import convert
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

SERVICE_START = "start"
CONF_SECONDS = "seconds"


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
