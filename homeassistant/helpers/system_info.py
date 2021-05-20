"""Helper to gather system info."""
from __future__ import annotations

import os
import platform
from typing import Any

from homeassistant.const import __version__ as current_version
from homeassistant.core import HomeAssistant
from homeassistant.loader import bind_hass
from homeassistant.util.package import is_virtual_env


@bind_hass
async def async_get_system_info(hass: HomeAssistant) -> dict[str, Any]:
    """Return info about the system."""
    info_object = {
        "installation_type": "Unknown",
        "version": current_version,
        "dev": "dev" in current_version,
        "hassio": hass.components.hassio.is_hassio(),
        "virtualenv": is_virtual_env(),
        "python_version": platform.python_version(),
        "docker": False,
        "arch": platform.machine(),
        "timezone": str(hass.config.time_zone),
        "os_name": platform.system(),
        "os_version": platform.release(),
    }

    if platform.system() == "Windows":
        info_object["os_version"] = platform.win32_ver()[0]
    elif platform.system() == "Darwin":
        info_object["os_version"] = platform.mac_ver()[0]
    elif platform.system() == "Linux":
        info_object["docker"] = os.path.isfile("/.dockerenv")

    # Determine installation type on current data
    if info_object["docker"]:
        info_object["installation_type"] = "Home Assistant Container"
    elif is_virtual_env():
        info_object["installation_type"] = "Home Assistant Core"

    # Enrich with Supervisor information
    if hass.components.hassio.is_hassio():
        info = hass.components.hassio.get_info()
        host = hass.components.hassio.get_host_info()

        info_object["supervisor"] = info.get("supervisor")
        info_object["host_os"] = host.get("operating_system")
        info_object["docker_version"] = info.get("docker")
        info_object["chassis"] = host.get("chassis")

        if info.get("hassos") is not None:
            info_object["installation_type"] = "Home Assistant OS"
        else:
            info_object["installation_type"] = "Home Assistant Supervised"

    return info_object
