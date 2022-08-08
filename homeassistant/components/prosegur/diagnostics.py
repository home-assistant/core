"""Diagnostics support for Prosegur."""
from __future__ import annotations

from typing import Any

from pyprosegur.installation import Installation

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"description", "latitude", "longitude", "contractId", "address"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    installation = await Installation.retrieve(hass.data[DOMAIN][entry.entry_id])

    activity = await installation.activity(hass.data[DOMAIN][entry.entry_id])

    return {
        "installation": async_redact_data(installation.data, TO_REDACT),
        "activity": activity,
    }
