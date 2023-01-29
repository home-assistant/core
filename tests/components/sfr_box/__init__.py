"""Tests for the SFR Box integration."""
from __future__ import annotations

from types import MappingProxyType

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_IDENTIFIERS,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_SW_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import ATTR_UNIQUE_ID, FIXED_ATTRIBUTES


def check_device_registry(
    device_registry: DeviceRegistry, expected_device: MappingProxyType
) -> None:
    """Ensure that the expected_device is correctly registered."""
    assert len(device_registry.devices) == 1
    registry_entry = device_registry.async_get_device(expected_device[ATTR_IDENTIFIERS])
    assert registry_entry is not None
    assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
    assert registry_entry.name == expected_device[ATTR_NAME]
    assert registry_entry.model == expected_device[ATTR_MODEL]
    assert registry_entry.sw_version == expected_device[ATTR_SW_VERSION]


def check_entities(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    expected_entities: MappingProxyType,
) -> None:
    """Ensure that the expected_entities are correct."""
    for expected_entity in expected_entities:
        entity_id = expected_entity[ATTR_ENTITY_ID]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state, f"Expected valid state for {entity_id}, got {state}"
        assert state.state == expected_entity[ATTR_STATE], (
            f"Expected state {expected_entity[ATTR_STATE]}, got {state.state} for"
            f" {entity_id}"
        )
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr), (
                f"Expected attribute {attr} == {expected_entity.get(attr)}, got"
                f" {state.attributes.get(attr)} for {entity_id}"
            )
