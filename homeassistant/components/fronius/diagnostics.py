"""Diagnostics support for Fronius."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import FroniusConfigEntry
from .coordinator import FroniusCoordinatorBase

TO_REDACT = {"unique_id", "serial"}


def _coordinator_data(
    coordinator: FroniusCoordinatorBase[Any] | None,
) -> dict[str, Any] | None:
    """Return the data of a SolarAPI coordinator as plain dicts."""
    if coordinator is None:
        return None
    return {
        solar_net_id: asdict(device_data)
        for solar_net_id, device_data in coordinator.data.items()
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: FroniusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    diag: dict[str, Any] = {}
    solar_net = config_entry.runtime_data
    fronius = solar_net.fronius

    diag["config_entry"] = config_entry.as_dict()
    diag["inverter_info"] = asdict(await fronius.inverter_info())

    diag["coordinators"] = {"inverters": {}}
    for inv in solar_net.inverter_coordinators:
        diag["coordinators"]["inverters"] |= _coordinator_data(inv) or {}

    diag["coordinators"]["logger"] = _coordinator_data(solar_net.logger_coordinator)
    diag["coordinators"]["meter"] = _coordinator_data(solar_net.meter_coordinator)
    diag["coordinators"]["ohmpilot"] = _coordinator_data(solar_net.ohmpilot_coordinator)
    diag["coordinators"]["power_flow"] = _coordinator_data(
        solar_net.power_flow_coordinator
    )
    diag["coordinators"]["storage"] = _coordinator_data(solar_net.storage_coordinator)

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
            for coordinator in solar_net.modbus.inverter_coordinators
        },
    }

    return async_redact_data(diag, TO_REDACT)
