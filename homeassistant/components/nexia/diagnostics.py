"""Diagnostics support for nexia."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_BRAND, DOMAIN
from .coordinator import NexiaDataUpdateCoordinator

TO_REDACT = {
    "dealer_contact_info",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: NexiaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    nexia_home = coordinator.nexia_home

    return {
        "entry": {
            "title": entry.title,
            "brand": entry.data.get(CONF_BRAND),
        },
        "automations": async_redact_data(nexia_home.automations_json, TO_REDACT),
        "devices": async_redact_data(nexia_home.devices_json, TO_REDACT),
    }
