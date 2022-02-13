"""Diagnostics support for Kostal Plenticore."""
from __future__ import annotations

from typing import Any

import attr

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .helper import Plenticore

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, dict[str, Any]]:
    """Return diagnostics for a config entry."""
    data = {"entry": async_redact_data(entry.as_dict(), TO_REDACT)}
    plenticore: Plenticore = hass.data[DOMAIN][entry.entry_id]

    # Get information from Kostal Plenticore library
    available_process_data = await plenticore.client.get_process_data()
    available_settings_data = await plenticore.client.get_settings()
    data["client"] = {
        "version": str(await plenticore.client.get_version()),
        "me": str(await plenticore.client.get_me()),
        "available_process_data": available_process_data,
        "available_settings_data": {
            module_id: [str(setting) for setting in settings]
            for module_id, settings in available_settings_data.items()
        },
    }

    # Gather information how this Plenticore device is represented in Home Assistant
    device_registry = dr.async_get(hass)
    hass_device = device_registry.async_get_device(
        identifiers=plenticore.device_info["identifiers"]
    )
    if not hass_device:
        return data

    data["device"] = {
        **attr.asdict(hass_device),
        "entities": {},
    }

    entity_registry = er.async_get(hass)
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
