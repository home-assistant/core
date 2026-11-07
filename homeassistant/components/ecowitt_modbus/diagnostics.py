"""Diagnostics support for Ecowitt Modbus."""

from typing import Any

from modbus_connection.model import Component

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import EcowittConfigEntry

# The host says where on the user's network the gateway is, and the rest all
# identify the specific unit. None of it is needed to interpret a reading.
#
# `device_id` is the WN90LP's raw identity register -- the same value
# `serial_number` is formatted from, and what `unique_id` is set to for a
# model that reports one. A model that reports none (the WN69LP) gets no
# unique_id at all, so there is nothing there to redact for it. Redacting
# `serial_number` alone would still leave the same value sitting in
# `device_id` and `unique_id` for a WN90LP.
TO_REDACT = {CONF_HOST, "device_id", "serial_number", "unique_id"}


def _values(component: Component) -> dict[str, Any]:
    """Every field a component decodes, whether or not it has an entity.

    Driven off the component's own field list rather than a copy of it here,
    so a reading added to the device library shows up in diagnostics without
    this needing to be updated.
    """
    return {name: getattr(component, name) for name in component.resolved_fields}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EcowittConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device

    return async_redact_data(
        {
            "entry": {
                "data": dict(entry.data),
                "unique_id": entry.unique_id,
            },
            "device": {
                "model": device.MODEL,
                "manufacturer": device.manufacturer,
                "serial_number": device.serial_number,
                "sw_version": device.sw_version,
            },
            "coordinator": {
                "last_update_success": coordinator.last_update_success,
                "scan_interval": str(coordinator.update_interval),
            },
            # The decoded live readings, including any the model exposes
            # that no entity surfaces.
            "readings": _values(device.sensors),
            # Identity and link settings. A wrong baud rate or sampling
            # period explains a lot of otherwise puzzling behaviour.
            "configuration": _values(device.info),
        },
        TO_REDACT,
    )
