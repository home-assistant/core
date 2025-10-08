"""Diagnostics support for ReCollect Waste."""

from __future__ import annotations

import dataclasses
from typing import Any

from aiorecollect.client import PickupEvent

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_PLACE_ID, DOMAIN

CONF_AREA_NAME = "area_name"
CONF_TITLE = "title"

TO_REDACT = {
    CONF_AREA_NAME,
    CONF_PLACE_ID,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[list[PickupEvent]] = hass.data[DOMAIN][
        entry.entry_id
    ]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": [dataclasses.asdict(event) for event in coordinator.data],
        },
        TO_REDACT,
    )
