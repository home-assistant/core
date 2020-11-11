"""Provide info to system health."""
from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback


@callback
def async_register(
    hass: HomeAssistant, register: system_health.SystemHealthRegistration
) -> None:
    """Register system health callbacks."""
    register.async_register_info(system_health_info, "/hassio")


async def system_health_info(hass: HomeAssistant):
    """Get info for the info page."""
    info = hass.components.hassio.get_info()
    host = hass.components.hassio.get_host_info()
    os = hass.components.hassio.get_os_info()
    supervisor = hass.components.hassio.get_supervisor_info()

    information = {
        "host_os": host.get("operating_system"),
        "update_channel": info.get("channel"),
        "supervisor_version": info.get("supervisor"),
        "docker_version": info.get("docker"),
        "chassis": host.get("chassis"),
        "disk_free": host.get("disk_free"),
        "disk_total": host.get("disk_total"),
        "disk_used": host.get("disk_used"),
        "healthy": supervisor.get("healthy"),
        "supported": supervisor.get("supported"),
    }

    if info.get("hassos") is not None:
        information["board"] = os.get("board")

    information["installed_addons"] = ", ".join(
        f"{addon['name']} ({addon['version']})"
        for addon in supervisor.get("addons", [])
    )

    return information
