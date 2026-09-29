"""Diagnostics support for the Greencell integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_SERIAL_NUMBER
from .models import GreencellConfigEntry

TO_REDACT = {CONF_SERIAL_NUMBER}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GreencellConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "access": {
            "disabled": runtime_data.access.is_disabled(),
            "can_execute": runtime_data.access.can_execute(),
        },
        "current": asdict(runtime_data.current_data),
        "voltage": asdict(runtime_data.voltage_data),
        "power": asdict(runtime_data.power_data),
        "state": asdict(runtime_data.state_data),
    }
