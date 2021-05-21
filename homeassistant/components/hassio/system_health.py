"""Provide info to system health."""
import os

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

SUPERVISOR_PING = f"http://{os.environ['HASSIO']}/supervisor/ping"
OBSERVER_URL = f"http://{os.environ['HASSIO']}:4357"


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/hassio")


async def system_health_info(hass: HomeAssistant):
    """Get info for the info page."""
    info = hass.components.hassio.get_info()
    host_info = hass.components.hassio.get_host_info()
    supervisor_info = hass.components.hassio.get_supervisor_info()

    if supervisor_info.get("healthy"):
        healthy = True
    else:
        healthy = {
            "type": "failed",
            "error": "Unhealthy",
            "more_info": "/hassio/system",
        }

    if supervisor_info.get("supported"):
        supported = True
    else:
        supported = {
            "type": "failed",
            "error": "Unsupported",
            "more_info": "/hassio/system",
        }

    information = {
        "host_os": host_info.get("operating_system"),
        "update_channel": info.get("channel"),
        "supervisor_version": f"supervisor-{info.get('supervisor')}",
        "docker_version": info.get("docker"),
        "disk_total": f"{host_info.get('disk_total')} GB",
        "disk_used": f"{host_info.get('disk_used')} GB",
        "healthy": healthy,
        "supported": supported,
    }

    if info.get("hassos") is not None:
        os_info = hass.components.hassio.get_os_info()
        information["board"] = os_info.get("board")

    information["supervisor_api"] = system_health.async_check_can_reach_url(
        hass, SUPERVISOR_PING, OBSERVER_URL
    )
    information["version_api"] = system_health.async_check_can_reach_url(
        hass,
        f"https://version.home-assistant.io/{info.get('channel')}.json",
        "/hassio/system",
    )

    information["installed_addons"] = ", ".join(
        f"{addon['name']} ({addon['version']})"
        for addon in supervisor_info.get("addons", [])
    )

    return information
