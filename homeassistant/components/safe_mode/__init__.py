"""The Safe Mode integration."""
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

DOMAIN = "safe_mode"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Safe Mode component."""
    persistent_notification.async_create(
        hass,
        "Home Assistant is running in safe mode. Check [the error log](/developer-tools/logs) to see what went wrong.",
        "Safe Mode",
    )
    return True
