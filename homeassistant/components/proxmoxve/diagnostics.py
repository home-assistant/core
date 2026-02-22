"""Diagnostics support for Proxmox VE."""

from __future__ import annotations

from typing import Any

from attr import asdict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import ProxmoxConfigEntry

TO_REDACT = [CONF_USERNAME, CONF_PASSWORD]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ProxmoxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a Proxmox VE config entry."""

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    devices = []

    registry_devices = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )

    for device in registry_devices:
        entities = []

        registry_entities = er.async_entries_for_device(
            entity_registry,
            device_id=device.id,
            include_disabled_entities=True,
        )

        for entity_entry in registry_entities:
            state_dict = None
            if state := hass.states.get(entity_entry.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)

            entities.append({"entry": asdict(entity_entry), "state": state_dict})

        devices.append({"device": asdict(device), "entities": entities})

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "devices": devices,
    }
