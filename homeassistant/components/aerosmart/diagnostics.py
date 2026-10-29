"""Diagnostics for aerosmart."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import AerosmartConfigEntry

TO_REDACT = {CONF_DEVICE, CONF_HOST}


def _report_diagnostics(coordinator: DataUpdateCoordinator[Any]) -> dict[str, Any]:
    """Return the serializable state of a coordinator report."""
    report = coordinator.data
    return {
        "last_update_success": coordinator.last_update_success,
        "updated_components": sorted(report.updated) if report else [],
        "failed_components": sorted(report.failed) if report else [],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AerosmartConfigEntry
) -> dict[str, Any]:
    """Return a redacted snapshot of the connection and update state."""
    del hass
    runtime = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "readings": _report_diagnostics(runtime.readings),
        "settings": _report_diagnostics(runtime.settings),
    }
