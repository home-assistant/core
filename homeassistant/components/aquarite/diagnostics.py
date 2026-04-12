"""Diagnostics support for Aquarite."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import AquariteConfigEntry

TO_REDACT_CONFIG = {CONF_USERNAME, CONF_PASSWORD}
TO_REDACT_COORDINATOR = {"city", "street", "zipcode", "lat", "lng", "email"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AquariteConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT_CONFIG),
        },
        "coordinator_data": async_redact_data(
            coordinator.data or {}, TO_REDACT_COORDINATOR
        ),
    }
