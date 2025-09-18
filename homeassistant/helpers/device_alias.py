# helpers/device_alias.py
from homeassistant.core import HomeAssistant

def resolve_device_alias(hass: HomeAssistant, alias: str) -> str | None:
    """Resolve a user-defined device alias to a device_id."""
    aliases = hass.data.get("device_aliases", {})
    return aliases.get(alias)