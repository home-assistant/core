"""Diagnostics support for energieleser."""

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant

from .coordinator import EnergieleserConfigEntry

TO_REDACT = {CONF_DEVICE_ID, "fabrication_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EnergieleserConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    device_data = coordinator.data

    device_data_dict = dataclasses.asdict(device_data)

    return async_redact_data(device_data_dict, TO_REDACT)
