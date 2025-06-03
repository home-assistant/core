"""Diagnostics support for Ridwell."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RidwellDataUpdateCoordinator

CONF_TITLE = "title"

TO_REDACT = {
    CONF_PASSWORD,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RidwellDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": [
                dataclasses.asdict(event)
                for events in coordinator.data.values()
                for event in events
            ],
        },
        TO_REDACT,
    )
