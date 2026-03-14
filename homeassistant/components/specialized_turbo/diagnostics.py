"""Diagnostics support for Specialized Turbo integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import SpecializedTurboConfigEntry
from .const import CONF_PIN

TO_REDACT = {CONF_PIN, CONF_ADDRESS}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: SpecializedTurboConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    snapshot = coordinator.snapshot

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "snapshot": {
            "message_count": snapshot.message_count,
            "battery": asdict(snapshot.battery),
            "motor": asdict(snapshot.motor),
            "settings": asdict(snapshot.settings),
        },
    }
