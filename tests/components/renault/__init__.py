"""Tests for the Renault integration."""
from __future__ import annotations

from types import MappingProxyType

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_SW_VERSION,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import (
    ATTR_UNIQUE_ID,
    DYNAMIC_ATTRIBUTES,
    FIXED_ATTRIBUTES,
    ICON_FOR_EMPTY_VALUES,
)


def get_no_data_icon(expected_entity: MappingProxyType):
    """Check icon attribute for inactive sensors."""
    entity_id = expected_entity[ATTR_ENTITY_ID]
    return ICON_FOR_EMPTY_VALUES.get(entity_id, expected_entity.get(ATTR_ICON))


def check_device_registry(
    device_registry: DeviceRegistry, expected_device: MappingProxyType
) -> None:
    """Ensure that the expected_device is correctly registered."""
    assert len(device_registry.devices) == 1
    registry_entry = device_registry.async_get_device(expected_device[ATTR_IDENTIFIERS])
    assert registry_entry is not None
    assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
    assert registry_entry.manufacturer == expected_device[ATTR_MANUFACTURER]
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
        assert state.state == expected_entity[ATTR_STATE]
        for attr in FIXED_ATTRIBUTES + DYNAMIC_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)


def check_entities_no_data(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    expected_entities: MappingProxyType,
    expected_state: str,
) -> None:
    """Ensure that the expected_entities are correct."""
    for expected_entity in expected_entities:
        entity_id = expected_entity[ATTR_ENTITY_ID]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state.state == expected_state
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)
        # Check dynamic attributes:
        assert state.attributes.get(ATTR_ICON) == get_no_data_icon(expected_entity)


def check_entities_unavailable(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    expected_entities: MappingProxyType,
) -> None:
    """Ensure that the expected_entities are correct."""
    for expected_entity in expected_entities:
        entity_id = expected_entity[ATTR_ENTITY_ID]
        registry_entry = entity_registry.entities.get(entity_id)
        assert registry_entry is not None, f"{entity_id} not found in registry"
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)
        # Check dynamic attributes:
        assert state.attributes.get(ATTR_ICON) == get_no_data_icon(expected_entity)
