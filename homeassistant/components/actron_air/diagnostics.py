"""Diagnostics support for Actron Air."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import ActronAirConfigEntry

TO_REDACT = {CONF_API_TOKEN, "master_serial", "serial_number", "serial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators: dict[int, Any] = {}
    for idx, coordinator in enumerate(entry.runtime_data.system_coordinators.values()):
        coordinators[idx] = {
            "system": async_redact_data(
                coordinator.system.model_dump(mode="json"), TO_REDACT
            ),
            "status": async_redact_data(
                coordinator.data.model_dump(mode="json", exclude={"last_known_state"}),
                TO_REDACT,
            ),
        }
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "coordinators": coordinators,
    }
