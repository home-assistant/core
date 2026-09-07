"""Diagnostics support for Fronius."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import FroniusConfigEntry

TO_REDACT = {"unique_id", "unique_identifier", "serial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: FroniusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}
    solar_net = config_entry.runtime_data
    fronius = solar_net.fronius

    diag["config_entry"] = config_entry.as_dict()
    diag["inverter_info"] = await fronius.inverter_info()

    diag["coordinators"] = {"inverters": {}}
    for inv in solar_net.inverter_coordinators:
        diag["coordinators"]["inverters"] |= inv.data

    diag["coordinators"]["logger"] = (
        solar_net.logger_coordinator.data if solar_net.logger_coordinator else None
    )
    diag["coordinators"]["meter"] = (
        solar_net.meter_coordinator.data if solar_net.meter_coordinator else None
    )
    diag["coordinators"]["ohmpilot"] = (
        solar_net.ohmpilot_coordinator.data if solar_net.ohmpilot_coordinator else None
    )
    diag["coordinators"]["power_flow"] = (
        solar_net.power_flow_coordinator.data
        if solar_net.power_flow_coordinator
        else None
    )
    diag["coordinators"]["storage"] = (
        solar_net.storage_coordinator.data if solar_net.storage_coordinator else None
    )

    diag["modbus"] = {
        "inverters": {
            coordinator.inverter_info.solar_net_id: {
                "float_mode": coordinator.modbus_inverter.float_mode,
                "has_storage": coordinator.modbus_inverter.has_storage,
                "model_chain": [
                    {
                        "model_id": model.model_id,
                        "address": model.address,
                        "length": model.length,
                    }
                    for model in coordinator.modbus_inverter.model_chain
                ],
                "data": coordinator.data,
            }
            for coordinator in solar_net.modbus_inverter_coordinators
        },
    }

    return async_redact_data(diag, TO_REDACT)
