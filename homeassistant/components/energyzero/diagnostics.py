"""Diagnostics support for EnergyZero."""

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import EnergyZeroConfigEntry, EnergyZeroData


def get_gas_price(data: EnergyZeroData, hours: int) -> float | None:
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
    hass: HomeAssistant, entry: EnergyZeroConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator_data = entry.runtime_data.data
    energy_today = coordinator_data.electricity_market_today
    all_in_today = coordinator_data.electricity_all_in_today

    return {
        "electricity_market": {
            "current_price": energy_today.current_price,
            "next_price": coordinator_data.next_price(
                energy_today, coordinator_data.electricity_market_tomorrow
            ),
            "average_price": energy_today.average_price,
            "max_price": energy_today.extreme_prices[1],
            "min_price": energy_today.extreme_prices[0],
            "highest_price_time": energy_today.highest_price_time_range.start_including,
            "lowest_price_time": energy_today.lowest_price_time_range.start_including,
            "percentage_of_max": energy_today.pct_of_max_price,
            "periods_priced_equal_or_lower": energy_today.time_ranges_priced_equal_or_lower,
        },
        "electricity_all_in": {
            "current_price": all_in_today.current_price,
            "next_price": coordinator_data.next_price(
                all_in_today, coordinator_data.electricity_all_in_tomorrow
            ),
            "average_price": all_in_today.average_price,
            "max_price": all_in_today.extreme_prices[1],
            "min_price": all_in_today.extreme_prices[0],
            "highest_price_time": all_in_today.highest_price_time_range.start_including,
            "lowest_price_time": all_in_today.lowest_price_time_range.start_including,
            "percentage_of_max": all_in_today.pct_of_max_price,
            "periods_priced_equal_or_lower": all_in_today.time_ranges_priced_equal_or_lower,
        },
        "gas": {
            "current_hour_price": get_gas_price(coordinator_data, 0),
            "next_hour_price": get_gas_price(coordinator_data, 1),
        },
    }
