"""Diagnostics support for energieleser."""

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import EnergieleserConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnergieleserConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    device_data = coordinator.data

    device_data_dict = dataclasses.asdict(device_data)

    return {
        "info": async_redact_data(entry.data, TO_REDACT),
        "data": device_data_dict,
    }
