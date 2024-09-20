"""Support for the Autarco diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import AutarcoConfigEntry, AutarcoDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AutarcoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    autarco_data: list[AutarcoDataUpdateCoordinator] = config_entry.runtime_data

    return {
        "sites_data": [
            {
                "id": coordinator.account_site.site_id,
                "name": coordinator.account_site.system_name,
                "health": coordinator.account_site.health,
                "solar": {
                    "power_production": coordinator.data.solar.power_production,
                    "energy_production_today": coordinator.data.solar.energy_production_today,
                    "energy_production_month": coordinator.data.solar.energy_production_month,
                    "energy_production_total": coordinator.data.solar.energy_production_total,
                },
                "inverters": [
                    {
                        "serial_number": inverter.serial_number,
                        "out_ac_power": inverter.out_ac_power,
                        "out_ac_energy_total": inverter.out_ac_energy_total,
                        "grid_turned_off": inverter.grid_turned_off,
                        "health": inverter.health,
                    }
                    for inverter in coordinator.data.inverters.values()
                ],
                **(
                    {
                        "battery": {
                            "flow_now": coordinator.data.battery.flow_now,
                            "net_charged_now": coordinator.data.battery.net_charged_now,
                            "state_of_charge": coordinator.data.battery.state_of_charge,
                            "discharged_today": coordinator.data.battery.discharged_today,
                            "discharged_month": coordinator.data.battery.discharged_month,
                            "discharged_total": coordinator.data.battery.discharged_total,
                            "charged_today": coordinator.data.battery.charged_today,
                            "charged_month": coordinator.data.battery.charged_month,
                            "charged_total": coordinator.data.battery.charged_total,
                        }
                    }
                    if coordinator.data.battery is not None
                    else {}
                ),
            }
            for coordinator in autarco_data
        ],
    }
