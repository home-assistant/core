"""Diagnostics support for Specialized Turbo."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant

from . import SpecializedTurboConfigEntry
from .const import CONF_HMI_HARDWARE, CONF_HMI_SERIAL, CONF_WRAPPED_KEY

TO_REDACT = {
    CONF_PIN,
    CONF_WRAPPED_KEY,
    CONF_HMI_HARDWARE,
    CONF_HMI_SERIAL,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: SpecializedTurboConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    snapshot = entry.runtime_data.snapshot

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "snapshot": {
            "message_count": snapshot.message_count,
            "battery": asdict(snapshot.battery),
            "motor": asdict(snapshot.motor),
            "settings": asdict(snapshot.settings),
            "system": asdict(snapshot.system),
        },
    }
