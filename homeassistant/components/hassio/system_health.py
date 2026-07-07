"""Provide info to system health."""

from collections.abc import Callable
import os
from typing import Any

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .coordinator import (
    get_addons_list,
    get_host_info,
    get_info,
    get_network_info,
    get_os_info,
    get_supervisor_info,
)
from .exceptions import HassioNotReadyError

SUPERVISOR_PING = "http://{ip_address}/supervisor/ping"
OBSERVER_URL = "http://{ip_address}:4357"


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info)


def _get_supervisor_data_if_available(
    hass: HomeAssistant, get_info_dict: Callable[[HomeAssistant], dict[str, Any]]
) -> dict[str, Any]:
    """Get data from supervisor if available."""
    try:
        return get_info_dict(hass)
    except HassioNotReadyError:
        return {}


async def system_health_info(hass: HomeAssistant) -> dict[str, Any]:
    """Get info for the info page."""
    ip_address = os.environ["SUPERVISOR"]
    info = _get_supervisor_data_if_available(hass, get_info)
    host_info = _get_supervisor_data_if_available(hass, get_host_info)
    supervisor_info = _get_supervisor_data_if_available(hass, get_supervisor_info)
    network_info = _get_supervisor_data_if_available(hass, get_network_info)
    try:
        addons_list = get_addons_list(hass)
    except HassioNotReadyError:
        addons_list = []

    healthy: bool | dict[str, str]
    if supervisor_info and supervisor_info.get("healthy"):
        healthy = True
    else:
        healthy = {
            "type": "failed",
            "error": "Unhealthy",
        }

    supported: bool | dict[str, str]
    if supervisor_info and supervisor_info.get("supported"):
        supported = True
    else:
        supported = {
            "type": "failed",
            "error": "Unsupported",
        }

    nameservers = set()
    for interface in network_info.get("interfaces", []):
        if not interface.get("primary"):
            continue
        if ipv4 := interface.get("ipv4"):
            nameservers.update(ipv4.get("nameservers", []))
        if ipv6 := interface.get("ipv6"):
            nameservers.update(ipv6.get("nameservers", []))

    information = {
        "host_os": host_info.get("operating_system"),
        "update_channel": info.get("channel"),
        "supervisor_version": f"supervisor-{info.get('supervisor')}",
        "agent_version": host_info.get("agent_version"),
        "docker_version": info.get("docker"),
        "disk_total": f"{host_info.get('disk_total')} GB",
        "disk_used": f"{host_info.get('disk_used')} GB",
        "nameservers": ", ".join(nameservers),
        "healthy": healthy,
        "supported": supported,
        "host_connectivity": network_info.get("host_internet"),
        "supervisor_connectivity": network_info.get("supervisor_internet"),
        "ntp_synchronized": host_info.get("dt_synchronized"),
        "virtualization": host_info.get("virtualization"),
    }

    if info.get("hassos") is not None:
        os_info = get_os_info(hass)
        information["board"] = os_info.get("board")

    if (disk_life_time := host_info.get("disk_life_time")) is not None:
        information["disk_life_time"] = f"{disk_life_time:.0f} %"

    # Not using aiohasupervisor for ping call below intentionally. Given system health
    # context, it seems preferable to do this check with minimal dependencies
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
        f"{addon['name']} ({addon['version']})" for addon in addons_list
    )

    return information
