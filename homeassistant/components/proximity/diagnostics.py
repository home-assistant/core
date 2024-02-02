"""Diagnostics support for Proximity."""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import ATTR_GPS, ATTR_IP, ATTR_MAC
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.person import ATTR_USER_ID
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import ProximityDataUpdateCoordinator

TO_REDACT = {
    ATTR_GPS,
    ATTR_IP,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MAC,
    ATTR_USER_ID,
    "context",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: ProximityDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    diag_data = {
        "entry": entry.as_dict(),
    }

    tracked_states: dict[str, dict] = {}
    for tracked_entity_id in coordinator.tracked_entities:
        if (state := hass.states.get(tracked_entity_id)) is None:
            continue
        tracked_states[tracked_entity_id] = state.as_dict()

    diag_data["data"] = {
        "proximity": coordinator.data.proximity,
        "entities": coordinator.data.entities,
        "entity_mapping": coordinator.entity_mapping,
        "tracked_states": async_redact_data(tracked_states, TO_REDACT),
    }
    return diag_data
