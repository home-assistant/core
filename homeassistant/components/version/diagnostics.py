"""Provides diagnostics for Version."""

from __future__ import annotations

from typing import Any

from attr import asdict

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .coordinator import VersionConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: VersionConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
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

        for entity in registry_entities:
            state_dict = None
            if state := hass.states.get(entity.entity_id):
                state_dict = dict(state.as_dict())
                state_dict.pop("context", None)

            entities.append({"entry": asdict(entity), "state": state_dict})

        devices.append({"device": asdict(device), "entities": entities})

    return {
        "entry": config_entry.as_dict(),
        "coordinator_data": {
            "version": coordinator.version,
            "version_data": coordinator.version_data,
        },
        "devices": devices,
    }
