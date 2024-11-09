"""Diagnostics support for La Marzocco."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, TypedDict

from pylamarzocco.const import FirmwareType

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import LaMarzoccoConfigEntry

TO_REDACT = {
    "serial_number",
}


class DiagnosticsData(TypedDict):
    """Diagnostic data for La Marzocco."""

    model: str
    config: dict[str, Any]
    firmware: list[dict[FirmwareType, dict[str, Any]]]
    statistics: dict[str, Any]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: LaMarzoccoConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.device
    # collect all data sources
    diagnostics_data = DiagnosticsData(
        model=device.model,
        config=asdict(device.config),
        firmware=[{key: asdict(firmware)} for key, firmware in device.firmware.items()],
        statistics=asdict(device.statistics),
    )

    return async_redact_data(diagnostics_data, TO_REDACT)
