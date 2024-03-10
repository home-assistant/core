"""Diagnostics support for P1 Monitor."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import P1MonitorDataUpdateCoordinator
from .const import (
    DOMAIN,
    SERVICE_PHASES,
    SERVICE_SETTINGS,
    SERVICE_SMARTMETER,
    SERVICE_WATERMETER,
)

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

TO_REDACT = {
    CONF_HOST,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: P1MonitorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    data = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "data": {
            "smartmeter": asdict(coordinator.data[SERVICE_SMARTMETER]),
            "phases": asdict(coordinator.data[SERVICE_PHASES]),
            "settings": asdict(coordinator.data[SERVICE_SETTINGS]),
        },
    }

    if coordinator.has_water_meter:
        data["data"]["watermeter"] = asdict(
            cast("DataclassInstance", coordinator.data[SERVICE_WATERMETER])
        )

    return data
