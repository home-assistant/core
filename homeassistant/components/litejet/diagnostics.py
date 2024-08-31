"""Support for LiteJet diagnostics."""
from typing import Any

from pylitejet import LiteJet

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for LiteJet config entry."""
    system: LiteJet = hass.data[DOMAIN]
    return {
        "loads": list(system.loads()),
        "button_switches": list(system.button_switches()),
        "scenes": list(system.scenes()),
        "connected": system.connected,
    }
