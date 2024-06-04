"""Provide info to system health."""

from __future__ import annotations

from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import system_info


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    info = await system_info.async_get_system_info(hass)

    return {
        "version": f"core-{info.get('version')}",
        "installation_type": info.get("installation_type"),
        "dev": info.get("dev"),
        "hassio": info.get("hassio"),
        "docker": info.get("docker"),
        "user": info.get("user"),
        "virtualenv": info.get("virtualenv"),
        "python_version": info.get("python_version"),
        "os_name": info.get("os_name"),
        "os_version": info.get("os_version"),
        "arch": info.get("arch"),
        "timezone": info.get("timezone"),
        "config_dir": hass.config.config_dir,
    }
