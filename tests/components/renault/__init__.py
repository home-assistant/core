"""Tests for the Renault integration."""
from __future__ import annotations

from types import MappingProxyType

from homeassistant.const import (
    ATTR_ICON,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_SW_VERSION,
)
from homeassistant.helpers.device_registry import DeviceRegistry

from .const import ICON_FOR_EMPTY_VALUES


def get_no_data_icon(expected_entity: MappingProxyType):
    """Check icon attribute for inactive sensors."""
    entity_id = expected_entity["entity_id"]
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
