"""Provide info to system health."""

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from . import get_instance


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    instance = get_instance(hass)
    run_history = instance.run_history
    return {
        "oldest_recorder_run": run_history.first.start,
        "current_recorder_run": run_history.current.start,
    }
