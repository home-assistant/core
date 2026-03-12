"""Support for Powerfox diagnostics."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from powerfox import DeviceReport, HeatMeter, PowerMeter, WaterMeter

from homeassistant.core import HomeAssistant

from .coordinator import PowerfoxConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PowerfoxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Powerfox config entry."""
    powerfox_data = entry.runtime_data

    return {
        "devices": [
            {
                **(
                    {
                        "power_meter": {
                            "outdated": coordinator.data.outdated,
                            "timestamp": datetime.strftime(
                                coordinator.data.timestamp, "%Y-%m-%d %H:%M:%S"
                            ),
                            "power": coordinator.data.power,
                            "energy_usage": coordinator.data.energy_usage,
                            "energy_return": coordinator.data.energy_return,
                            "energy_usage_high_tariff": coordinator.data.energy_usage_high_tariff,
                            "energy_usage_low_tariff": coordinator.data.energy_usage_low_tariff,
                        }
                    }
                    if isinstance(coordinator.data, PowerMeter)
                    else {}
                ),
                **(
                    {
                        "water_meter": {
                            "outdated": coordinator.data.outdated,
                            "timestamp": datetime.strftime(
                                coordinator.data.timestamp, "%Y-%m-%d %H:%M:%S"
                            ),
                            "cold_water": coordinator.data.cold_water,
                            "warm_water": coordinator.data.warm_water,
                        }
                    }
                    if isinstance(coordinator.data, WaterMeter)
                    else {}
                ),
                **(
                    {
                        "heat_meter": {
                            "outdated": coordinator.data.outdated,
                            "timestamp": datetime.strftime(
                                coordinator.data.timestamp, "%Y-%m-%d %H:%M:%S"
                            ),
                            "total_energy": coordinator.data.total_energy,
                            "delta_energy": coordinator.data.delta_energy,
                            "total_volume": coordinator.data.total_volume,
                            "delta_volume": coordinator.data.delta_volume,
                        }
                    }
                    if isinstance(coordinator.data, HeatMeter)
                    else {}
                ),
                **(
                    {
                        "gas_meter": {
                            "sum": coordinator.data.gas.sum,
                            "consumption": coordinator.data.gas.consumption,
                            "consumption_kwh": coordinator.data.gas.consumption_kwh,
                            "current_consumption": coordinator.data.gas.current_consumption,
                            "current_consumption_kwh": coordinator.data.gas.current_consumption_kwh,
                            "sum_currency": coordinator.data.gas.sum_currency,
                        }
                    }
                    if isinstance(coordinator.data, DeviceReport)
                    and coordinator.data.gas
                    else {}
                ),
            }
            for coordinator in powerfox_data
        ],
    }
