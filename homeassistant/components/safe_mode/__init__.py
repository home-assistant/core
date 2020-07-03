"""The Safe Mode integration."""
from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant

DOMAIN = "safe_mode"


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Safe Mode component."""
    persistent_notification.async_create(
        hass,
        "Asystent domowy działa w trybie awaryjnym. Sprawdź w [logach  systemu](/config/logs) "
        "co poszło nie tak.",
        "Tryb Awaryjny",
    )
    return True
