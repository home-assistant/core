"""Support for Powerfox Local diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PowerfoxLocalConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PowerfoxLocalConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Powerfox Local config entry."""
    coordinator = entry.runtime_data

    return {
        "power": coordinator.data.power,
        "energy_usage": coordinator.data.energy_usage,
        "energy_usage_high_tariff": coordinator.data.energy_usage_high_tariff,
        "energy_usage_low_tariff": coordinator.data.energy_usage_low_tariff,
        "energy_return": coordinator.data.energy_return,
    }
