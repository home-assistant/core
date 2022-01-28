"""Diagnostics support for P1 Monitor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import P1MonitorDataUpdateCoordinator
from .const import DOMAIN, SERVICE_PHASES, SERVICE_SETTINGS, SERVICE_SMARTMETER

TO_REDACT = {
    CONF_HOST,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: P1MonitorDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "data": {
            "smartmeter": coordinator.data[SERVICE_SMARTMETER].__dict__,
            "phases": coordinator.data[SERVICE_PHASES].__dict__,
            "settings": coordinator.data[SERVICE_SETTINGS].__dict__,
        },
    }
