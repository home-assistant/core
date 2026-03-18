"""Diagnostics support for P1 Monitor."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .const import (
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
    SERVICE_WATERMETER,
)
from .coordinator import P1MonitorConfigEntry

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

TO_REDACT = {CONF_HOST, CONF_PORT}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: P1MonitorConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "data": {
            "smartmeter": asdict(entry.runtime_data.data[SERVICE_SMARTMETER]),
            "phases": asdict(entry.runtime_data.data[SERVICE_PHASES]),
            "settings": asdict(entry.runtime_data.data[SERVICE_SETTINGS]),
        },
    }

    if entry.runtime_data.has_water_meter:
        data["data"]["watermeter"] = asdict(
            cast("DataclassInstance", entry.runtime_data.data[SERVICE_WATERMETER])
        )

    return data
