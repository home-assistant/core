"""Tests for 1-Wire integration."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock

from pyownet.protocol import ProtocolError

from homeassistant.components.onewire.const import DEFAULT_SYSBUS_MOUNT_DIR
from homeassistant.const import ATTR_ENTITY_ID, ATTR_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from .const import (
    ATTR_DEFAULT_DISABLED,
    ATTR_DEVICE_FILE,
    ATTR_INJECT_READS,
    ATTR_UNIQUE_ID,
    FIXED_ATTRIBUTES,
    MOCK_OWPROXY_DEVICES,
    MOCK_SYSBUS_DEVICES,
)


def check_and_enable_disabled_entities(
    entity_registry: EntityRegistry, expected_entities: MappingProxyType
) -> None:
    """Ensure that the expected_entities are correctly disabled."""
    for expected_entity in expected_entities:
        if expected_entity.get(ATTR_DEFAULT_DISABLED):
            entity_id = expected_entity[ATTR_ENTITY_ID]
            registry_entry = entity_registry.entities.get(entity_id)
            assert registry_entry.disabled
            assert registry_entry.disabled_by == "integration"
            entity_registry.async_update_entity(entity_id, **{"disabled_by": None})


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
        assert state.attributes[ATTR_DEVICE_FILE] == expected_entity.get(
            ATTR_DEVICE_FILE, registry_entry.unique_id
        )
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)


def setup_owproxy_mock_devices(
    owproxy: MagicMock, platform: str, device_ids: list(str)
) -> None:
    """Set up mock for owproxy."""
    dir_return_value = []
    main_read_side_effect = []
    sub_read_side_effect = []

    for device_id in device_ids:
        mock_device = MOCK_OWPROXY_DEVICES[device_id]

        # Setup directory listing
        dir_return_value += [f"/{device_id}/"]

        # Setup device reads
        main_read_side_effect += [device_id[0:2].encode()]
        if ATTR_INJECT_READS in mock_device:
            main_read_side_effect += mock_device[ATTR_INJECT_READS]

        # Setup sub-device reads
        device_sensors = mock_device.get(platform, [])
        for expected_sensor in device_sensors:
            sub_read_side_effect.append(expected_sensor[ATTR_INJECT_READS])

    # Ensure enough read side effect
    read_side_effect = (
        main_read_side_effect
        + sub_read_side_effect
        + [ProtocolError("Missing injected value")] * 20
    )
    owproxy.return_value.dir.return_value = dir_return_value
    owproxy.return_value.read.side_effect = read_side_effect


def setup_sysbus_mock_devices(
    platform: str, device_ids: list[str]
) -> tuple[list[str], list[Any]]:
    """Set up mock for sysbus."""
    glob_result = []
    read_side_effect = []

    for device_id in device_ids:
        mock_device = MOCK_SYSBUS_DEVICES[device_id]

        # Setup directory listing
        glob_result += [f"/{DEFAULT_SYSBUS_MOUNT_DIR}/{device_id}"]

        # Setup sub-device reads
        device_sensors = mock_device.get(platform, [])
        for expected_sensor in device_sensors:
            if isinstance(expected_sensor[ATTR_INJECT_READS], list):
                read_side_effect += expected_sensor[ATTR_INJECT_READS]
            else:
                read_side_effect.append(expected_sensor[ATTR_INJECT_READS])

    # Ensure enough read side effect
    read_side_effect.extend([FileNotFoundError("Missing injected value")] * 20)

    return (glob_result, read_side_effect)
