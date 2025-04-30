"""Diagnostics support for Actron Air Neo."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

TO_REDACT = {CONF_API_TOKEN, CONF_PASSWORD, CONF_USERNAME, "email", "id", "serial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Create a cleaned/redacted version of the API status data
    data = {
        "api_status": coordinator.data,
        "systems": coordinator.api.systems,
        "config_entry": entry.as_dict(),
    }

    # Redact sensitive information
    return async_redact_data(data, TO_REDACT)
