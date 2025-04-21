"""Diagnostics support for switchbot integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ENCRYPTION_KEY, CONF_KEY_ID
from .coordinator import SwitchbotConfigEntry

TO_REDACT = [CONF_KEY_ID, CONF_ENCRYPTION_KEY]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwitchbotConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device_info = {
        "address": coordinator.ble_device.address,
        "name": coordinator.device_name,
        "model": coordinator.model,
        "connectable": coordinator.connectable,
    }

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "device_info": device_info,
    }
