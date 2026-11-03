"""Diagnostics support for derivative."""

from typing import Any

from homeassistant.components.diagnostics import entity_entry_as_dict
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    registry = er.async_get(hass)
    entities = registry.entities.get_entries_for_config_entry_id(config_entry.entry_id)

    return {
        "config_entry": config_entry.as_dict(),
        "entity": [entity_entry_as_dict(entity) for entity in entities],
    }
