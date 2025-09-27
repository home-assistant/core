"""Diagnostics for the Portainer integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry

from . import PortainerConfigEntry

TO_REDACT = [CONF_API_TOKEN]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PortainerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Portainer config entry."""

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "coordinator_data": config_entry.runtime_data,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: PortainerConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a Portainer device."""
    entity_registry = er.async_get(hass)
    entities = entity_registry.entities.get_entries_for_device_id(device.id, True)

    return {
        "device": async_redact_data(device.dict_repr, TO_REDACT),
        "entities": [
            {
                "entity": entity.as_partial_dict,
                "state": state.as_dict()
                if (state := hass.states.get(entity.entity_id))
                else None,
            }
            for entity in entities
        ],
    }
