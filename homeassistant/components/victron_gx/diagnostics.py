"""Diagnostics support for victron_gx."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_INSTALLATION_ID, CONF_SERIAL
from .hub import VictronGxConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_SERIAL, CONF_INSTALLATION_ID}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VictronGxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = entry.runtime_data
    merged_config = {**entry.data, **entry.options}
    return {
        "entry_data": async_redact_data(merged_config, TO_REDACT),
        "devices": hub.get_diagnostics_data(),
    }
