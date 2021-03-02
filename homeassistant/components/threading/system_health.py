"""Provide threading info to system health."""
import sys
import threading
import traceback

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(async_system_health_info)


async def async_system_health_info(hass):
    """Get info for the info page."""
    frames = sys._current_frames()
    info = {}
    main_thread = threading.main_thread()
    for thread in threading.enumerate():
        if thread == main_thread:
            continue
        if thread.name in info:
            name = f"{thread.name} {thread.ident}"
        else:
            name = thread.name
        info[name] = "".join(traceback.format_stack(frames.get(thread.ident)))
    return info
