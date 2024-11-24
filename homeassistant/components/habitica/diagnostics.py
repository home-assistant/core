"""Diagnostics platform for Habitica integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_API_TOKEN,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from .const import CONF_API_USER
from .types import HabiticaConfigEntry

TO_REDACT = {
    CONF_USERNAME,
    CONF_EMAIL,
    CONF_API_TOKEN,
    CONF_PASSWORD,
    CONF_API_KEY,
    CONF_API_USER,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: HabiticaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    habitica_data = await config_entry.runtime_data.api.user.anonymized.get()

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "habitica_data": habitica_data,
    }
