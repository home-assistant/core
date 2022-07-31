"""Tests for 1-Wire integration."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock

from pyownet.protocol import ProtocolError

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_IDENTIFIERS,
    ATTR_MANUFACTURER,
    ATTR_MODEL,
    ATTR_NAME,
    ATTR_STATE,
    ATTR_VIA_DEVICE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry, RegistryEntryDisabler

from .const import (
    ATTR_DEFAULT_DISABLED,
    ATTR_DEVICE_FILE,
    ATTR_ENTITY_CATEGORY,
    ATTR_INJECT_READS,
    ATTR_UNIQUE_ID,
    FIXED_ATTRIBUTES,
    MOCK_OWPROXY_DEVICES,
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
            assert registry_entry.disabled_by is RegistryEntryDisabler.INTEGRATION
            entity_registry.async_update_entity(entity_id, **{"disabled_by": None})


def check_device_registry(
    device_registry: DeviceRegistry, expected_devices: list[MappingProxyType]
) -> None:
    """Ensure that the expected_devices are correctly registered."""
    for expected_device in expected_devices:
        registry_entry = device_registry.async_get_device(
            expected_device[ATTR_IDENTIFIERS]
        )
        assert registry_entry is not None
        assert registry_entry.identifiers == expected_device[ATTR_IDENTIFIERS]
        assert registry_entry.manufacturer == expected_device[ATTR_MANUFACTURER]
        assert registry_entry.name == expected_device[ATTR_NAME]
        assert registry_entry.model == expected_device[ATTR_MODEL]
        if expected_via_device := expected_device.get(ATTR_VIA_DEVICE):
            assert registry_entry.via_device_id is not None
            parent_entry = device_registry.async_get_device({expected_via_device})
            assert parent_entry is not None
            assert registry_entry.via_device_id == parent_entry.id
        else:
            assert registry_entry.via_device_id is None


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
        assert registry_entry.entity_category == expected_entity.get(
            ATTR_ENTITY_CATEGORY
        )
        assert registry_entry.unique_id == expected_entity[ATTR_UNIQUE_ID]
        state = hass.states.get(entity_id)
        assert state.state == expected_entity[ATTR_STATE]
        assert state.attributes[ATTR_DEVICE_FILE] == expected_entity.get(
            ATTR_DEVICE_FILE, registry_entry.unique_id
        )
        for attr in FIXED_ATTRIBUTES:
            assert state.attributes.get(attr) == expected_entity.get(attr)


def setup_owproxy_mock_devices(
    owproxy: MagicMock, platform: Platform, device_ids: list[str]
) -> None:
    """Set up mock for owproxy."""
    main_dir_return_value = []
    sub_dir_side_effect = []
    main_read_side_effect = []
    sub_read_side_effect = []

    for device_id in device_ids:
        _setup_owproxy_mock_device(
            main_dir_return_value,
            sub_dir_side_effect,
            main_read_side_effect,
            sub_read_side_effect,
            device_id,
            platform,
        )

    # Ensure enough read side effect
    dir_side_effect = [main_dir_return_value] + sub_dir_side_effect
    read_side_effect = (
        main_read_side_effect
        + sub_read_side_effect
        + [ProtocolError("Missing injected value")] * 20
    )
    owproxy.return_value.dir.side_effect = dir_side_effect
    owproxy.return_value.read.side_effect = read_side_effect


def _setup_owproxy_mock_device(
    main_dir_return_value: list,
    sub_dir_side_effect: list,
    main_read_side_effect: list,
    sub_read_side_effect: list,
    device_id: str,
    platform: Platform,
) -> None:
    """Set up mock for owproxy."""
    mock_device = MOCK_OWPROXY_DEVICES[device_id]

    # Setup directory listing
    main_dir_return_value += [f"/{device_id}/"]
    if "branches" in mock_device:
        # Setup branch directory listing
        for branch, branch_details in mock_device["branches"].items():
            sub_dir_side_effect.append(
                [  # dir on branch
                    f"/{device_id}/{branch}/{sub_device_id}/"
                    for sub_device_id in branch_details
                ]
            )

    _setup_owproxy_mock_device_reads(
        main_read_side_effect,
        sub_read_side_effect,
        mock_device,
        device_id,
        platform,
    )

    if "branches" in mock_device:
        for branch_details in mock_device["branches"].values():
            for sub_device_id, sub_device in branch_details.items():
                _setup_owproxy_mock_device_reads(
                    main_read_side_effect,
                    sub_read_side_effect,
                    sub_device,
                    sub_device_id,
                    platform,
                )


def _setup_owproxy_mock_device_reads(
    main_read_side_effect: list,
    sub_read_side_effect: list,
    mock_device: Any,
    device_id: str,
    platform: Platform,
) -> None:
    """Set up mock for owproxy."""
    # Setup device reads
    main_read_side_effect += [device_id[0:2].encode()]
    if ATTR_INJECT_READS in mock_device:
        main_read_side_effect += mock_device[ATTR_INJECT_READS]

    # Setup sub-device reads
    device_sensors = mock_device.get(platform, [])
    for expected_sensor in device_sensors:
        sub_read_side_effect.append(expected_sensor[ATTR_INJECT_READS])
