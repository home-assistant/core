"""Diagnostics support for easyEnergy."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import EasyEnergyDataUpdateCoordinator
from .const import DOMAIN
from .coordinator import EasyEnergyData


def get_gas_price(data: EasyEnergyData, hours: int) -> float | None:
    """Get the gas price for a given hour.

    Args:
        data: The data object.
        hours: The number of hours to add to the current time.

    Returns:
        The gas market price value.

    """
    if not data.gas_today:
        return None
    return data.gas_today.price_at_time(
        data.gas_today.utcnow() + timedelta(hours=hours)
    )


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EasyEnergyDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
        },
        "energy_usage": {
            "current_hour_price": coordinator.data.energy_today.current_usage_price,
            "next_hour_price": coordinator.data.energy_today.price_at_time(
                coordinator.data.energy_today.utcnow() + timedelta(hours=1)
            ),
            "average_price": coordinator.data.energy_today.average_usage_price,
            "max_price": coordinator.data.energy_today.extreme_usage_prices[1],
            "min_price": coordinator.data.energy_today.extreme_usage_prices[0],
            "highest_price_time": coordinator.data.energy_today.highest_usage_price_time,
            "lowest_price_time": coordinator.data.energy_today.lowest_usage_price_time,
            "percentage_of_max": coordinator.data.energy_today.pct_of_max_usage,
        },
        "energy_return": {
            "current_hour_price": coordinator.data.energy_today.current_return_price,
            "next_hour_price": coordinator.data.energy_today.price_at_time(
                coordinator.data.energy_today.utcnow() + timedelta(hours=1), "return"
            ),
            "average_price": coordinator.data.energy_today.average_return_price,
            "max_price": coordinator.data.energy_today.extreme_return_prices[1],
            "min_price": coordinator.data.energy_today.extreme_return_prices[0],
            "highest_price_time": coordinator.data.energy_today.highest_return_price_time,
            "lowest_price_time": coordinator.data.energy_today.lowest_return_price_time,
            "percentage_of_max": coordinator.data.energy_today.pct_of_max_return,
        },
        "gas": {
            "current_hour_price": get_gas_price(coordinator.data, 0),
            "next_hour_price": get_gas_price(coordinator.data, 1),
        },
    }
