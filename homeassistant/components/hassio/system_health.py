"""Provide info to system health."""

from __future__ import annotations

import os
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .data import get_host_info, get_info, get_os_info, get_supervisor_info

SUPERVISOR_PING = "http://{ip_address}/supervisor/ping"
OBSERVER_URL = "http://{ip_address}:4357"


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    ip_address = os.environ["SUPERVISOR"]
    info = get_info(hass) or {}
    host_info = get_host_info(hass) or {}
    supervisor_info = get_supervisor_info(hass)

    healthy: bool | dict[str, str]
    if supervisor_info is not None and supervisor_info.get("healthy"):
        healthy = True
    else:
        healthy = {
            "type": "failed",
            "error": "Unhealthy",
        }

    supported: bool | dict[str, str]
    if supervisor_info is not None and supervisor_info.get("supported"):
        supported = True
    else:
        supported = {
            "type": "failed",
            "error": "Unsupported",
        }

    information = {
        "host_os": host_info.get("operating_system"),
        "update_channel": info.get("channel"),
        "supervisor_version": f"supervisor-{info.get('supervisor')}",
        "agent_version": host_info.get("agent_version"),
        "docker_version": info.get("docker"),
        "disk_total": f"{host_info.get('disk_total')} GB",
        "disk_used": f"{host_info.get('disk_used')} GB",
        "healthy": healthy,
        "supported": supported,
    }

    if info.get("hassos") is not None:
        os_info = get_os_info(hass) or {}
        information["board"] = os_info.get("board")

    information["supervisor_api"] = system_health.async_check_can_reach_url(
        hass,
        SUPERVISOR_PING.format(ip_address=ip_address),
        OBSERVER_URL.format(ip_address=ip_address),
    )
    information["version_api"] = system_health.async_check_can_reach_url(
        hass,
        f"https://version.home-assistant.io/{info.get('channel')}.json",
    )

    information["installed_addons"] = ", ".join(
        f"{addon['name']} ({addon['version']})"
        for addon in (supervisor_info or {}).get("addons", [])
    )

    return information
