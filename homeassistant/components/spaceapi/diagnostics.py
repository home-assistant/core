"""Diagnostics support for SpaceAPI."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SpaceAPIConfigEntry

TO_REDACT = {"email", "phone", "sip", "issue_mail", "address", "lat", "lon"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SpaceAPIConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "config_entry_options": async_redact_data(dict(entry.options), TO_REDACT),
    }
