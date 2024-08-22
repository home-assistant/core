"""Diagnostics support for Hue."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .bridge import HueBridge


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    bridge: HueBridge = hass.data[DOMAIN][entry.entry_id]
    if bridge.api_version == 1:
        # diagnostics is only implemented for V2 bridges.
        return {}
    # Hue diagnostics are already redacted
    return await bridge.api.get_diagnostics()
