"""Helper to gather system info."""
import os
import platform
from typing import Dict

from homeassistant.const import __version__ as current_version
from homeassistant.loader import bind_hass
from homeassistant.util.package import is_virtual_env

from .typing import HomeAssistantType


@bind_hass
async def async_get_system_info(hass: HomeAssistantType) -> Dict:
    """Return info about the system."""
    info_object = {
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

    return info_object
