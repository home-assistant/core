"""Diagnostics platform for Traccar Server."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import TraccarServerCoordinator

KEYS_TO_REDACT = {CONF_ADDRESS, CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TraccarServerCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entity_registry = er.async_get(hass)

    entities = er.async_entries_for_config_entry(
        entity_registry,
        config_entry_id=config_entry.entry_id,
    )

    states_to_redact = {x["position"]["address"] for x in coordinator.data.values()}

    return async_redact_data(
        {
            "subscription_status": coordinator.client.subscription_status,
            "config_entry_options": dict(config_entry.options),
            "coordinator_data": coordinator.data,
            "entities": [
                {
                    "enity_id": entity.entity_id,
                    "disabled": entity.disabled,
                    "unit_of_measurement": entity.unit_of_measurement,
                    "state": {
                        "state": state.state
                        if state.state not in states_to_redact
                        else REDACTED,
                        "attributes": state.attributes,
                    },
                }
                for entity in entities
                if (state := hass.states.get(entity.entity_id)) is not None
            ],
        },
        KEYS_TO_REDACT,
    )


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: dr.DeviceEntry,
) -> dict[str, Any]:
    """Return device diagnostics."""
    coordinator: TraccarServerCoordinator = hass.data[DOMAIN][entry.entry_id]
    entity_registry = er.async_get(hass)

    entities = er.async_entries_for_device(
        entity_registry,
        device_id=device.id,
        include_disabled_entities=True,
    )

    states_to_redact = {x["position"]["address"] for x in coordinator.data.values()}

    # Enable all entitits to show everything in snapshots
    for entity in entities:
        entity_registry.async_update_entity(entity.entity_id, disabled_by=None)

    await hass.config_entries.async_reload(entry.entry_id)
    return async_redact_data(
        {
            "subscription_status": coordinator.client.subscription_status,
            "config_entry_options": dict(entry.options),
            "coordinator_data": coordinator.data,
            "entities": [
                {
                    "enity_id": entity.entity_id,
                    "disabled": entity.disabled,
                    "unit_of_measurement": entity.unit_of_measurement,
                    "state": {
                        "state": state.state
                        if state.state not in states_to_redact
                        else REDACTED,
                        "attributes": state.attributes,
                    },
                }
                for entity in entities
                if (state := hass.states.get(entity.entity_id)) is not None
            ],
        },
        KEYS_TO_REDACT,
    )
