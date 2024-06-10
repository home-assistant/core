"""Diagnostics support for Proximity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import ATTR_GPS, ATTR_IP, ATTR_MAC
from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.components.person import ATTR_USER_ID
from homeassistant.components.zone import DOMAIN as ZONE_DOMAIN
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .coordinator import ProximityConfigEntry

TO_REDACT = {
    ATTR_GPS,
    ATTR_IP,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_MAC,
    ATTR_USER_ID,
    "context",
    "location_name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ProximityConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    diag_data = {
        "entry": entry.as_dict(),
    }

    non_sensitiv_states = [
        STATE_HOME,
        STATE_NOT_HOME,
        STATE_UNAVAILABLE,
        STATE_UNKNOWN,
    ] + [z.name for z in hass.states.async_all(ZONE_DOMAIN)]

    tracked_states: dict[str, dict] = {}
    for tracked_entity_id in coordinator.tracked_entities:
        if (state := hass.states.get(tracked_entity_id)) is None:
            continue
        tracked_states[tracked_entity_id] = async_redact_data(
            state.as_dict(), TO_REDACT
        )
        if state.state not in non_sensitiv_states:
            tracked_states[tracked_entity_id]["state"] = REDACTED

    diag_data["data"] = {
        "proximity": coordinator.data.proximity,
        "entities": coordinator.data.entities,
        "entity_mapping": coordinator.entity_mapping,
        "tracked_states": tracked_states,
    }
    return diag_data
