"""SFR Box diagnostics platform."""
from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import DomainData

TO_REDACT = {"mac_addr", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "data": {
            "dsl": async_redact_data(dataclasses.asdict(data.dsl.data), TO_REDACT),
            "system": async_redact_data(
                dataclasses.asdict(data.system.data), TO_REDACT
            ),
        },
    }
