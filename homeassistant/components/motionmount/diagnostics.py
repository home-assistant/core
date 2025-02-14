"""Diagnostics support for MotionMount."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import MotionMountConfigEntry

TO_REDACT = [
    CONF_PIN,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: MotionMountConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(config_entry.data, TO_REDACT),
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: MotionMountConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    mm = config_entry.runtime_data

    return {"details": async_redact_data(mm.__dict__, TO_REDACT)}
