"""Diagnostics support for Tractive."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN, TRACKABLES

TO_REDACT = {CONF_PASSWORD, CONF_EMAIL, "title", "_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    trackables = hass.data[DOMAIN][config_entry.entry_id][TRACKABLES]

    diagnostics_data = async_redact_data(
        {
            "config_entry": config_entry.as_dict(),
            "trackables": [item.trackable for item in trackables],
        },
        TO_REDACT,
    )

    return diagnostics_data
