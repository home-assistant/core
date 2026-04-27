"""Diagnostics support for easyEnergy."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .coordinator import EasyEnergyConfigEntry, EasyEnergyData


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
    return data.gas_today.price_at_time(dt_util.utcnow() + timedelta(hours=hours))


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EasyEnergyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator_data = entry.runtime_data.data
    energy_today = coordinator_data.energy_today

    return {
        "entry": {
            "title": entry.title,
        },
        "energy_usage": {
            "current_hour_price": energy_today.current_price,
            "next_hour_price": energy_today.price_at_time(
                dt_util.utcnow() + timedelta(hours=1)
            ),
            "average_price": energy_today.average_price,
            "max_price": energy_today.extreme_prices[1],
            "min_price": energy_today.extreme_prices[0],
            "highest_price_time": energy_today.highest_price_time,
            "lowest_price_time": energy_today.lowest_price_time,
            "percentage_of_max": energy_today.pct_of_max,
        },
        "energy_return": {
            "current_hour_price": energy_today.current_return_price,
            "next_hour_price": energy_today.return_price_at_time(
                dt_util.utcnow() + timedelta(hours=1)
            ),
            "average_price": energy_today.average_return_price,
            "max_price": energy_today.extreme_return_prices[1],
            "min_price": energy_today.extreme_return_prices[0],
            "highest_price_time": energy_today.highest_return_price_time,
            "lowest_price_time": energy_today.lowest_return_price_time,
            "percentage_of_max": energy_today.pct_of_max_return,
        },
        "gas": {
            "current_hour_price": get_gas_price(coordinator_data, 0),
            "next_hour_price": get_gas_price(coordinator_data, 1),
        },
    }
