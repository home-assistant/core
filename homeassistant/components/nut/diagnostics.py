"""Diagnostics support for Nut."""

from __future__ import annotations

from typing import Any

import attr

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import NutConfigEntry
from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NutConfigEntry
) -> dict[str, dict[str, Any]]:
    """Return diagnostics for a config entry."""
    data = {"entry": async_redact_data(entry.as_dict(), TO_REDACT)}
    hass_data = entry.runtime_data

    # Get information from Nut library
    nut_data = hass_data.data
    nut_cmd = hass_data.user_available_commands
    data["nut_data"] = {
        "ups_list": nut_data.ups_list,
        "status": nut_data.status,
        "commands": nut_cmd,
    }

    # Gather information how this Nut device is represented in Home Assistant
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    hass_device = device_registry.async_get_device(
        identifiers={(DOMAIN, hass_data.unique_id)}
    )
    if not hass_device:
        return data

    data["device"] = {
        **attr.asdict(hass_device),
        "entities": {},
    }

    hass_entities = er.async_entries_for_device(
        entity_registry,
        device_id=hass_device.id,
        include_disabled_entities=True,
    )

    for entity_entry in hass_entities:
        state = hass.states.get(entity_entry.entity_id)
        state_dict = None
        if state:
            state_dict = dict(state.as_dict())
            # The entity_id is already provided at root level.
            state_dict.pop("entity_id", None)
            # The context doesn't provide useful information in this case.
            state_dict.pop("context", None)

        data["device"]["entities"][entity_entry.entity_id] = {
            **attr.asdict(
                entity_entry, filter=lambda attr, value: attr.name != "entity_id"
            ),
            "state": state_dict,
        }

    return data
