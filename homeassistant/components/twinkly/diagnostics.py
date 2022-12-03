"""Diagnostics support for Twinkly."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_IP_ADDRESS, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

TO_REDACT = [CONF_HOST, CONF_IP_ADDRESS, CONF_MAC]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Twinkly config entry."""

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    registry_devices = dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    )
    registry_entities = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    device = registry_devices.pop()
    entity = registry_entities.pop()
    state = hass.states.get(entity.entity_id)
    attributes: dict[Any, Any] = {}
    if state:
        attributes = state.attributes

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "sw_version": device.sw_version,
            "attributes": async_redact_data(attributes, TO_REDACT),
        },
    }
