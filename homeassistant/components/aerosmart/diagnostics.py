"""Diagnostics support for aerosmart."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .coordinator import AerosmartConfigEntry
from .sensor import SENSOR_DESCRIPTIONS

_TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AerosmartConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry without polling the device."""
    runtime = entry.runtime_data
    device = runtime.device

    def poll_diagnostics(coordinator: Any) -> dict[str, Any]:
        """Describe a poll which may still be awaiting its first result."""
        data = coordinator.data
        return {
            "last_update_success": (
                coordinator.last_update_success if data is not None else None
            ),
            "updated": sorted(data.updated) if data is not None else [],
            "failed": sorted(data.failed) if data is not None else [],
        }

    registers: dict[str, Any] = {}
    for description in SENSOR_DESCRIPTIONS:
        subsystem = getattr(device, description.component)
        registers[description.key] = getattr(subsystem, description.attribute)

    return {
        "entry_data": async_redact_data(
            {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
                "unit_ventilation": entry.data["unit_ventilation"],
                "unit_heat_pump": entry.data["unit_heat_pump"],
            },
            _TO_REDACT,
        ),
        "initial_refresh_completed": (
            runtime.initial_refresh_task is not None
            and runtime.initial_refresh_task.done()
        ),
        "polls": {
            "readings": poll_diagnostics(runtime.readings),
            "settings": poll_diagnostics(runtime.settings),
        },
        "registers": registers,
    }
