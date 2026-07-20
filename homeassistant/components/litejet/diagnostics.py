"""Support for LiteJet diagnostics."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import LiteJetConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LiteJetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for LiteJet config entry."""
    system = entry.runtime_data
    return {
        "model": system.model_name,
        "loads": list(system.loads()),
        "button_switches": list(system.button_switches()),
        "scenes": list(system.scenes()),
        "connected": system.connected,
    }
