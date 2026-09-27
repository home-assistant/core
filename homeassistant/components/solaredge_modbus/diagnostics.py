"""Diagnostics support for the SolarEdge Modbus integration."""

from typing import Any

from modbus_connection.model import Component, RegisterField

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import (
    SolarEdgeModbusConfigEntry,
    SolarEdgeModbusDataUpdateCoordinator,
)

TO_REDACT = {"serial_number"}


def _component_data(component: Component) -> dict[str, Any]:
    """Every decoded register field and computed property of a component.

    Only the classes below the library's own base count: its plumbing, such as
    the Modbus unit a component reads through, is not device data.
    """
    names = {
        name
        for klass in type(component).__mro__
        if issubclass(klass, Component) and klass is not Component
        for name, attribute in vars(klass).items()
        if not name.startswith("_") and isinstance(attribute, (RegisterField, property))
    }
    return {name: getattr(component, name) for name in sorted(names)}


def _poll_data(coordinator: SolarEdgeModbusDataUpdateCoordinator) -> dict[str, Any]:
    """What a coordinator's most recent poll got out of the device."""
    return {
        "updated": sorted(coordinator.data.updated),
        "failed": {
            subsystem: str(error)
            for subsystem, error in coordinator.data.failed.items()
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SolarEdgeModbusConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    What the inverter reports about itself and about what is attached to it,
    whether or not this integration has entities for it yet.
    """
    runtime_data = entry.runtime_data
    solaredge = runtime_data.solaredge

    data: dict[str, Any] = {
        "polls": {"readings": _poll_data(runtime_data.readings)},
        "common": _component_data(solaredge.common),
        "inverter": _component_data(solaredge.inverter),
        "mmppt": (
            [_component_data(module) for module in solaredge.mmppt.modules]
            if solaredge.mmppt is not None
            else None
        ),
        "meters": [_component_data(meter) for meter in solaredge.meters],
        "batteries": [_component_data(battery) for battery in solaredge.batteries],
        "unresponsive_blocks": sorted(solaredge.unresponsive_blocks),
    }

    return async_redact_data(data, TO_REDACT)
