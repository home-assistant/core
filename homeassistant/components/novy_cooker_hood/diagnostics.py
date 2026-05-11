"""Diagnostics support for the Novy Cooker Hood integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_TRANSMITTER


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    registry = er.async_get(hass)
    entities = registry.entities.get_entries_for_config_entry_id(config_entry.entry_id)
    transmitter = registry.async_get(config_entry.data[CONF_TRANSMITTER])
    transmitter_state = hass.states.get(transmitter.entity_id) if transmitter else None
    return {
        "config_entry": config_entry.as_dict(),
        "entities": [
            entity.extended_dict
            for entity in sorted(entities, key=lambda entity: entity.entity_id)
        ],
        "transmitter": {
            "entity_id": transmitter.entity_id if transmitter else None,
            "state": transmitter_state.as_dict() if transmitter_state else None,
        },
    }
