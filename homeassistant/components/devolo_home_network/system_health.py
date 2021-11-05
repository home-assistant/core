"""Provide info to system health."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    states: list[bool] = []
    firmware_updates_available = await asyncio.gather(
        *[
            entity["device"].device.async_check_firmware_available()
            for entity in hass.data[DOMAIN].values()
        ]
    )

    for result in firmware_updates_available:
        states.append(result["result"] == "UPDATE_AVAILABLE")

    return {"firmware_updates_available": any(states)}
