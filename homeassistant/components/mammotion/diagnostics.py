"""Diagnostics support for Mammotion."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import MammotionConfigEntry, MammotionMowerData

TO_REDACT: list[str] = []


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MammotionConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    mammotion_devices: list[MammotionMowerData] = entry.runtime_data
    data = {}
    for device in mammotion_devices:
        data[device.name] = asdict(device.reporting_coordinator.data)

    return async_redact_data(data, TO_REDACT)
