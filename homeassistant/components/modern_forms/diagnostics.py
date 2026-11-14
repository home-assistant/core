"""Diagnostics support for Modern Forms."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC
from homeassistant.core import HomeAssistant

from .coordinator import ModernFormsConfigEntry

REDACT_CONFIG = {CONF_MAC}
REDACT_DEVICE_INFO = {"mac_address", "owner"}
REDACT_DEVICE_STATUS = {"name", "schedule", "user_data"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ModernFormsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "device": {
            "info": async_redact_data(
                asdict(coordinator.modern_forms.info), REDACT_DEVICE_INFO
            ),
            "status": async_redact_data(
                asdict(coordinator.modern_forms.status), REDACT_DEVICE_STATUS
            ),
        },
    }
