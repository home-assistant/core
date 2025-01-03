"""Tests for the Device Registry."""

from collections.abc import Iterable
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime
from functools import partial
import time
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from yarl import URL

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ReleaseChannel
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_capture_events, flush_store


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry and add it to hass."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    return entry


async def test_get_or_create_returns_same_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure we do not duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:66:77:88")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    game_room_area = area_registry.async_get_area_by_name("Game Room")
    assert game_room_area is not None
    assert len(area_registry.areas) == 1

    assert len(device_registry.devices) == 1
    assert entry.area_id == game_room_area.id
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry.identifiers == {("bridgeid", "0123")}

    assert entry2.area_id == game_room_area.id

    assert entry3.manufacturer == "manufacturer"
    assert entry3.model == "model"
    assert entry3.name == "name"
    assert entry3.sw_version == "sw-version"
    assert entry3.suggested_area == "Game Room"
    assert entry3.area_id == game_room_area.id

    await hass.async_block_till_done()

    # Only 2 update events. The third entry did not generate any changes.
    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {"connections": {("mac", "12:34:56:ab:cd:ef")}},
    }


async def test_requirement_for_identifier_or_connection(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure we do require some descriptor of device."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers=set(),
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections=set(),
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 2
    assert entry
    assert entry2

    with pytest.raises(HomeAssistantError):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            connections=set(),
            identifiers=set(),
            manufacturer="manufacturer",
            model="model",
        )


async def test_multiple_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry2.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry2.primary_config_entry == config_entry_1.entry_id
    assert entry3.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry3.primary_config_entry == config_entry_1.entry_id


async def test_multiple_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    config_entry_1 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.config_entries == {config_entry_1.entry_id}
    assert entry.config_subentries == {config_entry_1.entry_id: None}
    entry_id = entry.id

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        config_subentry_id=None,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.id == entry_id
    assert entry.config_entries == {config_entry_1.entry_id}
    assert entry.config_subentries == {config_entry_1.entry_id: None}

    with pytest.raises(HomeAssistantError):
        device_registry.async_get_or_create(
            config_entry_id=config_entry_1.entry_id,
            config_subentry_id="mock-subentry-id-1-1",
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
            identifiers={("bridgeid", "0123")},
            manufacturer="manufacturer",
            model="model",
        )

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        config_subentry_id="mock-subentry-id-2-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.id == entry_id
    assert entry.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry.config_subentries == {
        config_entry_1.entry_id: None,
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_loading_from_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading stored devices on start."""
    created_at = "2024-01-01T00:00:00+00:00"
    modified_at = "2024-02-01T00:00:00+00:00"
    hass_storage[dr.STORAGE_KEY] = {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "data": {
            "devices": [
                {
                    "area_id": "12345A",
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": "https://example.com/config",
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": created_at,
                    "disabled_by": dr.DeviceEntryDisabler.USER,
                    "entry_type": dr.DeviceEntryType.SERVICE,
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": {"label1", "label2"},
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "model_id": "model_id",
                    "modified_at": modified_at,
                    "name_by_user": "Test Friendly Name",
                    "name": "name",
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": "serial_no",
                    "sw_version": "version",
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [
                {
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "connections": [["Zigbee", "23.45.67.89.01"]],
                    "created_at": created_at,
                    "id": "bcdefghijklmn",
                    "identifiers": [["serial", "3456ABCDEF12"]],
                    "modified_at": modified_at,
                    "orphaned_timestamp": None,
                }
            ],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 1

    assert registry.deleted_devices["bcdefghijklmn"] == dr.DeletedDeviceEntry(
        config_entries={mock_config_entry.entry_id},
        config_subentries={mock_config_entry.entry_id: None},
        connections={("Zigbee", "23.45.67.89.01")},
        created_at=datetime.fromisoformat(created_at),
        id="bcdefghijklmn",
        identifiers={("serial", "3456ABCDEF12")},
        modified_at=datetime.fromisoformat(modified_at),
        orphaned_timestamp=None,
    )

    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry == dr.DeviceEntry(
        area_id="12345A",
        config_entries={mock_config_entry.entry_id},
        config_subentries={mock_config_entry.entry_id: None},
        configuration_url="https://example.com/config",
        connections={("Zigbee", "01.23.45.67.89")},
        created_at=datetime.fromisoformat(created_at),
        disabled_by=dr.DeviceEntryDisabler.USER,
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version",
        id="abcdefghijklm",
        identifiers={("serial", "123456ABCDEF")},
        labels={"label1", "label2"},
        manufacturer="manufacturer",
        model="model",
        model_id="model_id",
        modified_at=datetime.fromisoformat(modified_at),
        name_by_user="Test Friendly Name",
        name="name",
        primary_config_entry=mock_config_entry.entry_id,
        serial_number="serial_no",
        suggested_area=None,  # Not stored
        sw_version="version",
    )
    assert isinstance(entry.config_entries, set)
    assert isinstance(entry.connections, set)
    assert isinstance(entry.identifiers, set)

    # Restore a device, id should be reused from the deleted device entry
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "23.45.67.89.01")},
        identifiers={("serial", "3456ABCDEF12")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry == dr.DeviceEntry(
        config_entries={mock_config_entry.entry_id},
        config_subentries={mock_config_entry.entry_id: None},
        connections={("Zigbee", "23.45.67.89.01")},
        created_at=datetime.fromisoformat(created_at),
        id="bcdefghijklmn",
        identifiers={("serial", "3456ABCDEF12")},
        manufacturer="manufacturer",
        model="model",
        modified_at=utcnow(),
        primary_config_entry=mock_config_entry.entry_id,
    )
    assert entry.id == "bcdefghijklmn"
    assert isinstance(entry.config_entries, set)
    assert isinstance(entry.connections, set)
    assert isinstance(entry.identifiers, set)


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_1(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.1."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "data": {
            "devices": [
                {
                    "config_entries": [mock_config_entry.entry_id],
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "entry_type": "service",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "sw_version": "version",
                },
                # Invalid entry type
                {
                    "config_entries": ["234567"],
                    "connections": [],
                    "entry_type": "INVALID_VALUE",
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "sw_version": None,
                },
            ],
            "deleted_devices": [
                {
                    "config_entries": ["123456"],
                    "connections": [],
                    "entry_type": "service",
                    "id": "deletedid",
                    "identifiers": [["serial", "123456ABCDFF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "sw_version": "version",
                }
            ],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)
    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": [],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "model_id": None,
                    "modified_at": utcnow().isoformat(),
                    "name": "name",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [
                {
                    "config_entries": ["123456"],
                    "config_subentries": {"123456": None},
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "id": "deletedid",
                    "identifiers": [["serial", "123456ABCDFF"]],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "orphaned_timestamp": None,
                }
            ],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_2(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.2."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "modified_at": utcnow().isoformat(),
                    "name": "name",
                    "name_by_user": None,
                    "sw_version": "version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "manufacturer": None,
                    "model": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)

    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": [],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "model_id": None,
                    "modified_at": utcnow().isoformat(),
                    "name": "name",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_fom_1_3(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.3."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 3,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "sw_version": "version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "manufacturer": None,
                    "model": None,
                    "name_by_user": None,
                    "name": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)

    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": [],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "model_id": None,
                    "modified_at": utcnow().isoformat(),
                    "name": "name",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name": None,
                    "name_by_user": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_4(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.4."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 4,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "manufacturer": None,
                    "model": None,
                    "name_by_user": None,
                    "name": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)

    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": [],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "model_id": None,
                    "modified_at": utcnow().isoformat(),
                    "name": "name",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_5(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.5."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 5,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": ["blah"],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": ["blah"],
                    "manufacturer": None,
                    "model": None,
                    "name_by_user": None,
                    "name": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)

    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": ["blah"],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "model_id": None,
                    "modified_at": utcnow().isoformat(),
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": ["blah"],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_6(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.6."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 6,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": ["blah"],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": ["blah"],
                    "manufacturer": None,
                    "model": None,
                    "name_by_user": None,
                    "primary_config_entry": None,
                    "name": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)

    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": ["blah"],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": ["blah"],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_7(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.7."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 7,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": ["blah"],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "model_id": None,
                    "name": "name",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": ["blah"],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "name_by_user": None,
                    "primary_config_entry": None,
                    "name": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
        sw_version="new_version",
    )
    assert entry.id == "abcdefghijklm"

    # Check we store migrated data
    await flush_store(registry._store)

    assert hass_storage[dr.STORAGE_KEY] == {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_subentries": {mock_config_entry.entry_id: None},
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": ["blah"],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_subentries": {"234567": None},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "invalid-entry-type",
                    "identifiers": [["serial", "mock-id-invalid-entry"]],
                    "labels": ["blah"],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }


async def test_removing_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 2
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}

    device_registry.async_clear_config_entry(config_entry_1.entry_id)
    entry = device_registry.async_get_device(identifiers={("bridgeid", "0123")})
    entry3_removed = device_registry.async_get_device(
        identifiers={("bridgeid", "4567")}
    )

    assert entry.config_entries == {config_entry_2.entry_id}
    assert entry3_removed is None

    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: None},
        },
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry3.id,
    }
    assert update_events[3].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id, config_entry_2.entry_id},
            "config_subentries": {
                config_entry_1.entry_id: None,
                config_entry_2.entry_id: None,
            },
            "primary_config_entry": config_entry_1.entry_id,
        },
    }
    assert update_events[4].data == {
        "action": "remove",
        "device_id": entry3.id,
    }


async def test_deleted_device_removing_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 2
    assert len(device_registry.deleted_devices) == 0
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}

    device_registry.async_remove_device(entry.id)
    device_registry.async_remove_device(entry3.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    await hass.async_block_till_done()
    assert len(update_events) == 5
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry2.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: None},
        },
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry3.id,
    }
    assert update_events[3].data == {
        "action": "remove",
        "device_id": entry.id,
    }
    assert update_events[4].data == {
        "action": "remove",
        "device_id": entry3.id,
    }

    device_registry.async_clear_config_entry(config_entry_1.entry_id)
    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    device_registry.async_clear_config_entry(config_entry_2.entry_id)
    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    # No event when a deleted device is purged
    await hass.async_block_till_done()
    assert len(update_events) == 5

    # Re-add, expect to keep the device id
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry2.id

    future_time = time.time() + dr.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        device_registry.async_purge_expired_orphaned_devices()

    # Re-add, expect to get a new device id after the purge
    entry4 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry3.id != entry4.id


async def test_removing_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry4 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        config_subentry_id="mock-subentry-id-2-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert entry.id == entry4.id
    assert entry4.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry4.config_subentries == {
        config_entry_1.entry_id: None,
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }

    device_registry.async_clear_config_subentry(
        config_entry_1.entry_id, "mock-subentry-id-1-1"
    )
    entry = device_registry.async_get_device(identifiers={("bridgeid", "0123")})
    assert entry.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry.config_subentries == {
        config_entry_1.entry_id: None,
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }

    device_registry.async_clear_config_subentry(config_entry_1.entry_id, None)
    entry = device_registry.async_get_device(identifiers={("bridgeid", "0123")})
    assert entry.config_entries == {config_entry_2.entry_id}
    assert entry.config_subentries == {
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }

    device_registry.async_clear_config_subentry(
        config_entry_2.entry_id, "mock-subentry-id-2-1"
    )
    assert device_registry.async_get_device(identifiers={("bridgeid", "0123")}) is None
    assert device_registry.async_get_device(identifiers={("bridgeid", "4567")}) is None

    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: None},
            "identifiers": {("bridgeid", "0123")},
        },
    }
    assert update_events[2].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id, config_entry_2.entry_id},
            "config_subentries": {
                config_entry_1.entry_id: None,
                config_entry_2.entry_id: "mock-subentry-id-2-1",
            },
            "primary_config_entry": config_entry_1.entry_id,
        },
    }
    assert update_events[3].data == {
        "action": "remove",
        "device_id": entry.id,
    }


async def test_deleted_device_removing_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry4 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        config_subentry_id="mock-subentry-id-2-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0
    assert entry.id == entry4.id
    assert entry4.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry4.config_subentries == {
        config_entry_1.entry_id: None,
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 3
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: None},
            "identifiers": {("bridgeid", "0123")},
        },
    }
    assert update_events[2].data == {
        "action": "remove",
        "device_id": entry.id,
    }

    entry = device_registry.deleted_devices.get_entry({("bridgeid", "0123")}, None)
    assert entry.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry.config_subentries == {
        config_entry_1.entry_id: None,
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }
    assert entry.orphaned_timestamp is None

    device_registry.async_clear_config_subentry(config_entry_1.entry_id, None)
    entry = device_registry.deleted_devices.get_entry({("bridgeid", "0123")}, None)
    assert entry.config_entries == {config_entry_2.entry_id}
    assert entry.config_subentries == {
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }
    assert entry.orphaned_timestamp is None

    # Remove the same subentry again
    device_registry.async_clear_config_subentry(config_entry_1.entry_id, None)
    assert (
        device_registry.deleted_devices.get_entry({("bridgeid", "0123")}, None) is entry
    )

    device_registry.async_clear_config_subentry(
        config_entry_2.entry_id, "mock-subentry-id-2-1"
    )
    entry = device_registry.deleted_devices.get_entry({("bridgeid", "0123")}, None)
    assert entry.config_entries == set()
    assert entry.config_subentries == {}
    assert entry.orphaned_timestamp is not None

    # No event when a deleted device is purged
    await hass.async_block_till_done()
    assert len(update_events) == 3

    # Re-add, expect to keep the device id
    restored_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        config_subentry_id="mock-subentry-id-2-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert restored_entry.id == entry.id

    # Remove again, and trigger purge
    device_registry.async_remove_device(entry.id)
    device_registry.async_clear_config_subentry(
        config_entry_2.entry_id, "mock-subentry-id-2-1"
    )
    entry = device_registry.deleted_devices.get_entry({("bridgeid", "0123")}, None)
    assert entry.config_entries == set()
    assert entry.config_subentries == {}
    assert entry.orphaned_timestamp is not None

    future_time = time.time() + dr.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        device_registry.async_purge_expired_orphaned_devices()

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 0

    # Re-add, expect to get a new device id after the purge
    new_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert new_entry.id != entry.id


async def test_removing_area_id(
    device_registry: dr.DeviceRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Make sure we can clear area id."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    entry_w_area = device_registry.async_update_device(entry.id, area_id="12345A")

    device_registry.async_clear_area_id("12345A")
    entry_wo_area = device_registry.async_get_device(identifiers={("bridgeid", "0123")})

    assert not entry_wo_area.area_id
    assert entry_w_area != entry_wo_area


async def test_specifying_via_device_create(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test specifying a via_device and removal of the hub device."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    via = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    light = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id == via.id

    device_registry.async_remove_device(via.id)
    light = device_registry.async_get_device(identifiers={("hue", "456")})
    assert light.via_device_id is None

    # A device with a non existing via_device reference should create
    light_via_nonexisting_parent_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "789")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "non_existing_123"),
    )
    assert {
        "calls `device_registry.async_get_or_create` "
        "referencing a non existing `via_device` "
        '("hue","non_existing_123")' in caplog.text
    }
    assert light_via_nonexisting_parent_device is not None
    assert light_via_nonexisting_parent_device.via_device_id is None
    nonexisting_parent_device = device_registry.async_get_device(
        identifiers={("hue", "non_existing_123")}
    )
    assert nonexisting_parent_device is None


async def test_specifying_via_device_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test specifying a via_device and updating."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    light = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        name="Light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id is None

    via = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    light = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id == via.id
    assert light.name == "Light"

    # Try updating with a non existing via device
    light = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        name="New light",
        via_device=("hue", "non_existing_abc"),
    )
    assert {
        "calls `device_registry.async_get_or_create` "
        "referencing a non existing `via_device` "
        '("hue","non_existing_123")' in caplog.text
    }
    # Assert the name was updated correctly
    assert light.via_device_id == via.id
    assert light.name == "New light"


async def test_loading_saving_data(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we load/save data correctly."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)
    config_entry_3 = MockConfigEntry()
    config_entry_3.add_to_hass(hass)
    config_entry_4 = MockConfigEntry()
    config_entry_4.add_to_hass(hass)
    config_entry_5 = MockConfigEntry()
    config_entry_5.add_to_hass(hass)

    orig_via = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
        name="Original Name",
        sw_version="Orig SW 1",
        entry_type=None,
    )

    orig_light = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    orig_light2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections=set(),
        identifiers={("hue", "789")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    device_registry.async_remove_device(orig_light2.id)

    orig_light3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_3.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("hue", "abc")},
        manufacturer="manufacturer",
        model="light",
    )

    device_registry.async_get_or_create(
        config_entry_id=config_entry_4.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("abc", "123")},
        manufacturer="manufacturer",
        model="light",
    )

    device_registry.async_remove_device(orig_light3.id)

    orig_light4 = device_registry.async_get_or_create(
        config_entry_id=config_entry_3.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("hue", "abc")},
        manufacturer="manufacturer",
        model="light",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    assert orig_light4.id == orig_light3.id

    orig_kitchen_light = device_registry.async_get_or_create(
        config_entry_id=config_entry_5.entry_id,
        connections=set(),
        identifiers={("hue", "999")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
        disabled_by=dr.DeviceEntryDisabler.USER,
        suggested_area="Kitchen",
    )

    assert len(device_registry.devices) == 4
    assert len(device_registry.deleted_devices) == 1

    orig_via = device_registry.async_update_device(
        orig_via.id,
        area_id="mock-area-id",
        name_by_user="mock-name-by-user",
        labels={"mock-label1", "mock-label2"},
    )

    # Now load written data in new registry
    registry2 = dr.DeviceRegistry(hass)
    await flush_store(device_registry._store)
    await registry2.async_load()

    # Ensure same order
    assert list(device_registry.devices) == list(registry2.devices)
    assert list(device_registry.deleted_devices) == list(registry2.deleted_devices)

    new_via = registry2.async_get_device(identifiers={("hue", "0123")})
    new_light = registry2.async_get_device(identifiers={("hue", "456")})
    new_light4 = registry2.async_get_device(identifiers={("hue", "abc")})

    assert orig_via == new_via
    assert orig_light == new_light
    assert orig_light4 == new_light4

    # Ensure enums converted
    for old, new in (
        (orig_via, new_via),
        (orig_light, new_light),
        (orig_light4, new_light4),
    ):
        assert old.disabled_by is new.disabled_by
        assert old.entry_type is new.entry_type

    # Ensure a save/load cycle does not keep suggested area
    new_kitchen_light = registry2.async_get_device(identifiers={("hue", "999")})
    assert orig_kitchen_light.suggested_area == "Kitchen"

    orig_kitchen_light_witout_suggested_area = device_registry.async_update_device(
        orig_kitchen_light.id, suggested_area=None
    )
    assert orig_kitchen_light_witout_suggested_area.suggested_area is None
    assert orig_kitchen_light_witout_suggested_area == new_kitchen_light


async def test_no_unnecessary_changes(
    device_registry: dr.DeviceRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Make sure we do not consider devices changes."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("hue", "456"), ("bla", "123")},
    )
    with patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_schedule_save"
    ) as mock_save:
        entry2 = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id, identifiers={("hue", "456")}
        )

    assert entry.id == entry2.id
    assert len(mock_save.mock_calls) == 0


async def test_format_mac(
    device_registry: dr.DeviceRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Make sure we normalize mac addresses."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for mac in ("123456ABCDEF", "123456abcdef", "12:34:56:ab:cd:ef", "1234.56ab.cdef"):
        test_entry = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        )
        assert test_entry.id == entry.id, mac
        assert test_entry.connections == {
            (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
        }

    # This should not raise
    for invalid in (
        "invalid_mac",
        "123456ABCDEFG",  # 1 extra char
        "12:34:56:ab:cdef",  # not enough :
        "12:34:56:ab:cd:e:f",  # too many :
        "1234.56abcdef",  # not enough .
        "123.456.abc.def",  # too many .
    ):
        invalid_mac_entry = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, invalid)},
        )
        assert list(invalid_mac_entry.connections)[0][1] == invalid


async def test_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Verify that we can update some attributes of a device."""
    created_at = datetime.fromisoformat("2024-01-01T01:00:00+00:00")
    freezer.move_to(created_at)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "456"), ("bla", "123")},
    )
    new_connections = {(dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA")}
    new_identifiers = {("hue", "654"), ("bla", "321")}
    assert not entry.area_id
    assert not entry.labels
    assert not entry.name_by_user
    assert entry.created_at == created_at
    assert entry.modified_at == created_at

    modified_at = datetime.fromisoformat("2024-02-01T01:00:00+00:00")
    freezer.move_to(modified_at)
    with patch.object(device_registry, "async_schedule_save") as mock_save:
        updated_entry = device_registry.async_update_device(
            entry.id,
            area_id="12345A",
            configuration_url="https://example.com/config",
            disabled_by=dr.DeviceEntryDisabler.USER,
            entry_type=dr.DeviceEntryType.SERVICE,
            hw_version="hw_version",
            labels={"label1", "label2"},
            manufacturer="Test Producer",
            model="Test Model",
            model_id="Test Model Name",
            name_by_user="Test Friendly Name",
            name="name",
            new_connections=new_connections,
            new_identifiers=new_identifiers,
            serial_number="serial_no",
            suggested_area="suggested_area",
            sw_version="version",
            via_device_id="98765B",
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry == dr.DeviceEntry(
        area_id="12345A",
        config_entries={mock_config_entry.entry_id},
        config_subentries={mock_config_entry.entry_id: None},
        configuration_url="https://example.com/config",
        connections={("mac", "65:43:21:fe:dc:ba")},
        created_at=created_at,
        disabled_by=dr.DeviceEntryDisabler.USER,
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version",
        id=entry.id,
        identifiers={("bla", "321"), ("hue", "654")},
        labels={"label1", "label2"},
        manufacturer="Test Producer",
        model="Test Model",
        model_id="Test Model Name",
        modified_at=modified_at,
        name_by_user="Test Friendly Name",
        name="name",
        serial_number="serial_no",
        suggested_area="suggested_area",
        sw_version="version",
        via_device_id="98765B",
    )

    assert device_registry.async_get_device(identifiers={("hue", "456")}) is None
    assert device_registry.async_get_device(identifiers={("bla", "123")}) is None

    assert (
        device_registry.async_get_device(identifiers={("hue", "654")}) == updated_entry
    )
    assert (
        device_registry.async_get_device(identifiers={("bla", "321")}) == updated_entry
    )

    assert (
        device_registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")}
        )
        is None
    )
    assert (
        device_registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA")}
        )
        == updated_entry
    )

    assert device_registry.async_get(updated_entry.id) is not None

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "area_id": None,
            "connections": {("mac", "12:34:56:ab:cd:ef")},
            "configuration_url": None,
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "identifiers": {("bla", "123"), ("hue", "456")},
            "labels": set(),
            "manufacturer": None,
            "model": None,
            "model_id": None,
            "name": None,
            "name_by_user": None,
            "serial_number": None,
            "suggested_area": None,
            "sw_version": None,
            "via_device_id": None,
        },
    }
    with pytest.raises(HomeAssistantError):
        device_registry.async_update_device(
            entry.id,
            merge_connections=new_connections,
            new_connections=new_connections,
        )

    with pytest.raises(HomeAssistantError):
        device_registry.async_update_device(
            entry.id,
            merge_identifiers=new_identifiers,
            new_identifiers=new_identifiers,
        )


@pytest.mark.parametrize(
    ("initial_connections", "new_connections", "updated_connections"),
    [
        (  # No connection -> single connection
            None,
            {(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
            {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
        ),
        (  # No connection -> double connection
            None,
            {
                (dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA"),
                (dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF"),
            },
            {
                (dr.CONNECTION_NETWORK_MAC, "65:43:21:fe:dc:ba"),
                (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef"),
            },
        ),
        (  # single connection -> no connection
            {(dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA")},
            set(),
            set(),
        ),
        (  # single connection -> single connection
            {(dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA")},
            {(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
            {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
        ),
        (  # single connection -> double connection
            {(dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA")},
            {
                (dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA"),
                (dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF"),
            },
            {
                (dr.CONNECTION_NETWORK_MAC, "65:43:21:fe:dc:ba"),
                (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef"),
            },
        ),
        (  # Double connection -> None
            {
                (dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF"),
                (dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA"),
            },
            set(),
            set(),
        ),
        (  # Double connection -> single connection
            {
                (dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA"),
                (dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF"),
            },
            {(dr.CONNECTION_NETWORK_MAC, "65:43:21:FE:DC:BA")},
            {(dr.CONNECTION_NETWORK_MAC, "65:43:21:fe:dc:ba")},
        ),
    ],
)
async def test_update_connection(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    initial_connections: set[tuple[str, str]] | None,
    new_connections: set[tuple[str, str]] | None,
    updated_connections: set[tuple[str, str]] | None,
) -> None:
    """Verify that we can update some attributes of a device."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections=initial_connections,
        identifiers={("hue", "456"), ("bla", "123")},
    )

    with patch.object(device_registry, "async_schedule_save") as mock_save:
        updated_entry = device_registry.async_update_device(
            entry.id,
            new_connections=new_connections,
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry.connections == updated_connections
    assert (
        device_registry.async_get_device(identifiers={("bla", "123")}) == updated_entry
    )


async def test_update_remove_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)
    config_entry_3 = MockConfigEntry()
    config_entry_3.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )
    entry4 = device_registry.async_update_device(
        entry2.id, add_config_entry_id=config_entry_3.entry_id
    )
    # Try to add an unknown config entry
    with pytest.raises(HomeAssistantError):
        device_registry.async_update_device(entry2.id, add_config_entry_id="blabla")

    assert len(device_registry.devices) == 2
    assert entry.id == entry2.id == entry4.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry4.config_entries == {
        config_entry_1.entry_id,
        config_entry_2.entry_id,
        config_entry_3.entry_id,
    }

    device_registry.async_update_device(
        entry2.id, remove_config_entry_id=config_entry_1.entry_id
    )
    updated_entry = device_registry.async_update_device(
        entry2.id, remove_config_entry_id=config_entry_3.entry_id
    )
    removed_entry = device_registry.async_update_device(
        entry3.id, remove_config_entry_id=config_entry_1.entry_id
    )

    assert updated_entry.config_entries == {config_entry_2.entry_id}
    assert removed_entry is None

    removed_entry = device_registry.async_get_device(identifiers={("bridgeid", "4567")})

    assert removed_entry is None

    await hass.async_block_till_done()

    assert len(update_events) == 7
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry2.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: None},
        },
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry3.id,
    }
    assert update_events[3].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id, config_entry_2.entry_id},
            "config_subentries": {
                config_entry_1.entry_id: None,
                config_entry_2.entry_id: None,
            },
        },
    }
    assert update_events[4].data == {
        "action": "update",
        "device_id": entry2.id,
        "changes": {
            "config_entries": {
                config_entry_1.entry_id,
                config_entry_2.entry_id,
                config_entry_3.entry_id,
            },
            "config_subentries": {
                config_entry_1.entry_id: None,
                config_entry_2.entry_id: None,
                config_entry_3.entry_id: None,
            },
            "primary_config_entry": config_entry_1.entry_id,
        },
    }
    assert update_events[5].data == {
        "action": "update",
        "device_id": entry2.id,
        "changes": {
            "config_entries": {config_entry_2.entry_id, config_entry_3.entry_id},
            "config_subentries": {
                config_entry_2.entry_id: None,
                config_entry_3.entry_id: None,
            },
        },
    }
    assert update_events[6].data == {
        "action": "remove",
        "device_id": entry3.id,
    }


async def test_update_remove_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we do not get duplicate entries."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2-1",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry_2.add_to_hass(hass)
    config_entry_3 = MockConfigEntry()
    config_entry_3.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        config_subentry_id="mock-subentry-id-1-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry_id = entry.id
    assert entry.config_entries == {config_entry_1.entry_id}
    assert entry.config_subentries == {config_entry_1.entry_id: "mock-subentry-id-1-1"}

    # Try adding the same subentry again
    assert (
        device_registry.async_update_device(
            entry_id,
            add_config_entry_id=config_entry_1.entry_id,
            add_config_subentry_id="mock-subentry-id-1-1",
        )
        is entry
    )

    entry = device_registry.async_update_device(
        entry_id,
        add_config_entry_id=config_entry_2.entry_id,
        add_config_subentry_id="mock-subentry-id-2-1",
    )
    assert entry.config_entries == {config_entry_1.entry_id, config_entry_2.entry_id}
    assert entry.config_subentries == {
        config_entry_1.entry_id: "mock-subentry-id-1-1",
        config_entry_2.entry_id: "mock-subentry-id-2-1",
    }

    entry = device_registry.async_update_device(
        entry_id,
        add_config_entry_id=config_entry_3.entry_id,
        add_config_subentry_id=None,
    )
    assert entry.config_entries == {
        config_entry_1.entry_id,
        config_entry_2.entry_id,
        config_entry_3.entry_id,
    }
    assert entry.config_subentries == {
        config_entry_1.entry_id: "mock-subentry-id-1-1",
        config_entry_2.entry_id: "mock-subentry-id-2-1",
        config_entry_3.entry_id: None,
    }

    # Try to add a subentry without specifying entry
    with pytest.raises(
        HomeAssistantError,
        match="Can't add config subentry without specifying config entry",
    ):
        device_registry.async_update_device(entry_id, add_config_subentry_id="blabla")

    # Try to add an unknown subentry
    with pytest.raises(
        HomeAssistantError,
        match=f"Config entry {config_entry_3.entry_id} has no subentry blabla",
    ):
        device_registry.async_update_device(
            entry_id,
            add_config_entry_id=config_entry_3.entry_id,
            add_config_subentry_id="blabla",
        )

    assert len(device_registry.devices) == 1

    entry = device_registry.async_update_device(
        entry_id,
        remove_config_entry_id=config_entry_1.entry_id,
    )
    assert entry.config_entries == {
        config_entry_2.entry_id,
        config_entry_3.entry_id,
    }
    assert entry.config_subentries == {
        config_entry_2.entry_id: "mock-subentry-id-2-1",
        config_entry_3.entry_id: None,
    }

    # Try removing the same subentry again
    assert (
        device_registry.async_update_device(
            entry_id,
            remove_config_entry_id=config_entry_1.entry_id,
        )
        is entry
    )

    entry = device_registry.async_update_device(
        entry_id,
        remove_config_entry_id=config_entry_2.entry_id,
    )
    assert entry.config_entries == {config_entry_3.entry_id}
    assert entry.config_subentries == {
        config_entry_3.entry_id: None,
    }

    entry = device_registry.async_update_device(
        entry_id,
        remove_config_entry_id=config_entry_3.entry_id,
    )
    assert entry is None

    await hass.async_block_till_done()

    assert len(update_events) == 6
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry_id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry_id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: "mock-subentry-id-1-1"},
        },
    }
    assert update_events[2].data == {
        "action": "update",
        "device_id": entry_id,
        "changes": {
            "config_entries": {config_entry_1.entry_id, config_entry_2.entry_id},
            "config_subentries": {
                config_entry_1.entry_id: "mock-subentry-id-1-1",
                config_entry_2.entry_id: "mock-subentry-id-2-1",
            },
        },
    }
    assert update_events[3].data == {
        "action": "update",
        "device_id": entry_id,
        "changes": {
            "config_entries": {
                config_entry_1.entry_id,
                config_entry_2.entry_id,
                config_entry_3.entry_id,
            },
            "config_subentries": {
                config_entry_1.entry_id: "mock-subentry-id-1-1",
                config_entry_2.entry_id: "mock-subentry-id-2-1",
                config_entry_3.entry_id: None,
            },
            "primary_config_entry": config_entry_1.entry_id,
        },
    }
    assert update_events[4].data == {
        "action": "update",
        "device_id": entry_id,
        "changes": {
            "config_entries": {config_entry_2.entry_id, config_entry_3.entry_id},
            "config_subentries": {
                config_entry_2.entry_id: "mock-subentry-id-2-1",
                config_entry_3.entry_id: None,
            },
        },
    }
    assert update_events[5].data == {
        "action": "remove",
        "device_id": entry_id,
    }


async def test_update_suggested_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Verify that we can update the suggested area version of a device."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bla", "123")},
    )
    assert not entry.suggested_area
    assert entry.area_id is None

    suggested_area = "Pool"

    with patch.object(device_registry, "async_schedule_save") as mock_save:
        updated_entry = device_registry.async_update_device(
            entry.id, suggested_area=suggested_area
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry.suggested_area == suggested_area

    pool_area = area_registry.async_get_area_by_name("Pool")
    assert pool_area is not None
    assert updated_entry.area_id == pool_area.id
    assert len(area_registry.areas) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {"area_id": None, "suggested_area": None},
    }

    # Do not save or fire the event if the suggested
    # area does not result in a change of area
    # but still update the actual entry
    with patch.object(device_registry, "async_schedule_save") as mock_save_2:
        updated_entry = device_registry.async_update_device(
            entry.id, suggested_area="Other"
        )
    assert len(update_events) == 2
    assert mock_save_2.call_count == 0
    assert updated_entry != entry
    assert updated_entry.suggested_area == "Other"


async def test_cleanup_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup works."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)
    ghost_config_entry = MockConfigEntry()
    ghost_config_entry.add_to_hass(hass)

    d1 = device_registry.async_get_or_create(
        identifiers={("hue", "d1")}, config_entry_id=config_entry.entry_id
    )
    device_registry.async_get_or_create(
        identifiers={("hue", "d2")}, config_entry_id=config_entry.entry_id
    )
    d3 = device_registry.async_get_or_create(
        identifiers={("hue", "d3")}, config_entry_id=config_entry.entry_id
    )
    device_registry.async_get_or_create(
        identifiers={("something", "d4")}, config_entry_id=ghost_config_entry.entry_id
    )
    # Remove the config entry without triggering the normal cleanup
    hass.config_entries._entries.pop(ghost_config_entry.entry_id)

    entity_registry.async_get_or_create("light", "hue", "e1", device_id=d1.id)
    entity_registry.async_get_or_create("light", "hue", "e2", device_id=d1.id)
    entity_registry.async_get_or_create("light", "hue", "e3", device_id=d3.id)

    # Manual cleanup should detect the orphaned config entry
    dr.async_cleanup(hass, device_registry, entity_registry)

    assert device_registry.async_get_device(identifiers={("hue", "d1")}) is not None
    assert device_registry.async_get_device(identifiers={("hue", "d2")}) is not None
    assert device_registry.async_get_device(identifiers={("hue", "d3")}) is not None
    assert device_registry.async_get_device(identifiers={("something", "d4")}) is None


async def test_cleanup_device_registry_removes_expired_orphaned_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test cleanup removes expired orphaned devices."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        identifiers={("hue", "d1")}, config_entry_id=config_entry.entry_id
    )
    device_registry.async_get_or_create(
        identifiers={("hue", "d2")}, config_entry_id=config_entry.entry_id
    )
    device_registry.async_get_or_create(
        identifiers={("hue", "d3")}, config_entry_id=config_entry.entry_id
    )

    device_registry.async_clear_config_entry(config_entry.entry_id)
    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 3

    dr.async_cleanup(hass, device_registry, entity_registry)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 3

    future_time = time.time() + dr.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        dr.async_cleanup(hass, device_registry, entity_registry)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 0


async def test_cleanup_startup(hass: HomeAssistant) -> None:
    """Test we run a cleanup on startup."""
    hass.set_state(CoreState.not_running)

    with patch(
        "homeassistant.helpers.device_registry.Debouncer.async_call"
    ) as mock_call:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


@pytest.mark.parametrize("load_registries", [False])
async def test_cleanup_entity_registry_change(hass: HomeAssistant) -> None:
    """Test we run a cleanup when entity registry changes.

    Don't pre-load the registries as the debouncer will then not be waiting for
    EVENT_ENTITY_REGISTRY_UPDATED events.
    """
    await dr.async_load(hass)
    await er.async_load(hass)
    ent_reg = er.async_get(hass)

    with patch(
        "homeassistant.helpers.device_registry.Debouncer.async_schedule_call"
    ) as mock_call:
        entity = ent_reg.async_get_or_create("light", "hue", "e1")
        await hass.async_block_till_done()
        assert len(mock_call.mock_calls) == 0

        # Normal update does not trigger
        ent_reg.async_update_entity(entity.entity_id, name="updated")
        await hass.async_block_till_done()
        assert len(mock_call.mock_calls) == 0

        # Device ID update triggers
        ent_reg.async_get_or_create("light", "hue", "e1", device_id="bla")
        await hass.async_block_till_done()
        assert len(mock_call.mock_calls) == 1

        # Removal also triggers
        ent_reg.async_remove(entity.entity_id)
        await hass.async_block_till_done()
        assert len(mock_call.mock_calls) == 2


async def test_restore_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure device id is stable."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry3.id
    assert entry.id != entry2.id
    assert len(device_registry.devices) == 2
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "device_id": entry.id,
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry2.id,
    }
    assert update_events[3].data == {
        "action": "create",
        "device_id": entry3.id,
    }


async def test_restore_simple_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure device id is stable."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    assert entry.id == entry3.id
    assert entry.id != entry2.id
    assert len(device_registry.devices) == 2
    assert len(device_registry.deleted_devices) == 0

    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "device_id": entry.id,
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry2.id,
    }
    assert update_events[3].data == {
        "action": "create",
        "device_id": entry3.id,
    }


async def test_restore_shared_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure device id is stable for shared devices."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_234", "2345")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry2.id
    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry2.config_entries, set)
    assert isinstance(entry2.connections, set)
    assert isinstance(entry2.identifiers, set)

    device_registry.async_remove_device(entry.id)

    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_234", "2345")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry3.id
    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    entry4 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry4.id
    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry4.config_entries, set)
    assert isinstance(entry4.connections, set)
    assert isinstance(entry4.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 7
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_1.entry_id},
            "config_subentries": {config_entry_1.entry_id: None},
            "identifiers": {("entry_123", "0123")},
        },
    }
    assert update_events[2].data == {
        "action": "remove",
        "device_id": entry.id,
    }
    assert update_events[3].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[4].data == {
        "action": "remove",
        "device_id": entry.id,
    }
    assert update_events[5].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[6].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": {
            "config_entries": {config_entry_2.entry_id},
            "config_subentries": {config_entry_2.entry_id: None},
            "identifiers": {("entry_234", "2345")},
        },
    }


async def test_get_or_create_empty_then_set_default_values(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an entry, then setting default name, model, manufacturer."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert entry.name is None
    assert entry.model is None
    assert entry.manufacturer is None

    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"

    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 2",
        default_model="default model 2",
        default_manufacturer="default manufacturer 2",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"


async def test_get_or_create_empty_then_update(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an entry, then setting name, model, manufacturer."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert entry.name is None
    assert entry.model is None
    assert entry.manufacturer is None

    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="name 1",
        model="model 1",
        manufacturer="manufacturer 1",
    )
    assert entry.name == "name 1"
    assert entry.model == "model 1"
    assert entry.manufacturer == "manufacturer 1"

    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "name 1"
    assert entry.model == "model 1"
    assert entry.manufacturer == "manufacturer 1"


async def test_get_or_create_sets_default_values(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating an entry, then setting default name, model, manufacturer."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"

    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 2",
        default_model="default model 2",
        default_manufacturer="default manufacturer 2",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"


async def test_verify_suggested_area_does_not_overwrite_area_id(
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Make sure suggested area does not override a set area id."""
    game_room_area = area_registry.async_create("Game Room")

    original_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
    )
    entry = device_registry.async_update_device(
        original_entry.id, area_id=game_room_area.id
    )

    assert entry.area_id == game_room_area.id

    entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="New Game Room",
    )
    assert entry2.area_id == game_room_area.id


async def test_disable_config_entry_disables_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we disable entities tied to a config entry."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)

    entry1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    assert not entry1.disabled
    assert entry2.disabled

    await hass.config_entries.async_set_disabled_by(
        config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entry1 = device_registry.async_get(entry1.id)
    assert entry1.disabled
    assert entry1.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    entry2 = device_registry.async_get(entry2.id)
    assert entry2.disabled
    assert entry2.disabled_by is dr.DeviceEntryDisabler.USER

    await hass.config_entries.async_set_disabled_by(config_entry.entry_id, None)
    await hass.async_block_till_done()

    entry1 = device_registry.async_get(entry1.id)
    assert not entry1.disabled
    entry2 = device_registry.async_get(entry2.id)
    assert entry2.disabled
    assert entry2.disabled_by is dr.DeviceEntryDisabler.USER


async def test_only_disable_device_if_all_config_entries_are_disabled(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we only disable device if all related config entries are disabled."""
    config_entry1 = MockConfigEntry(domain="light")
    config_entry1.add_to_hass(hass)
    config_entry2 = MockConfigEntry(domain="light")
    config_entry2.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    entry1 = device_registry.async_get_or_create(
        config_entry_id=config_entry2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert len(entry1.config_entries) == 2
    assert not entry1.disabled

    await hass.config_entries.async_set_disabled_by(
        config_entry1.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entry1 = device_registry.async_get(entry1.id)
    assert not entry1.disabled

    await hass.config_entries.async_set_disabled_by(
        config_entry2.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    entry1 = device_registry.async_get(entry1.id)
    assert entry1.disabled
    assert entry1.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    await hass.config_entries.async_set_disabled_by(config_entry1.entry_id, None)
    await hass.async_block_till_done()

    entry1 = device_registry.async_get(entry1.id)
    assert not entry1.disabled


@pytest.mark.parametrize(
    ("configuration_url", "expectation"),
    [
        ("http://localhost", nullcontext()),
        ("http://localhost:8123", nullcontext()),
        ("https://example.com", nullcontext()),
        ("http://localhost/config", nullcontext()),
        ("http://localhost:8123/config", nullcontext()),
        ("https://example.com/config", nullcontext()),
        ("homeassistant://config", nullcontext()),
        (URL("http://localhost"), nullcontext()),
        (URL("http://localhost:8123"), nullcontext()),
        (URL("https://example.com"), nullcontext()),
        (URL("http://localhost/config"), nullcontext()),
        (URL("http://localhost:8123/config"), nullcontext()),
        (URL("https://example.com/config"), nullcontext()),
        (URL("homeassistant://config"), nullcontext()),
        (None, nullcontext()),
        ("http://", pytest.raises(ValueError)),
        ("https://", pytest.raises(ValueError)),
        ("gopher://localhost", pytest.raises(ValueError)),
        ("homeassistant://", pytest.raises(ValueError)),
        (URL("http://"), pytest.raises(ValueError)),
        (URL("https://"), pytest.raises(ValueError)),
        (URL("gopher://localhost"), pytest.raises(ValueError)),
        (URL("homeassistant://"), pytest.raises(ValueError)),
        # Exception implements __str__
        (Exception("https://example.com"), nullcontext()),
        (Exception("https://"), pytest.raises(ValueError)),
        (Exception(), pytest.raises(ValueError)),
    ],
)
async def test_device_info_configuration_url_validation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    configuration_url: str | URL | None,
    expectation: AbstractContextManager,
) -> None:
    """Test configuration URL of device info is properly validated."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    with expectation:
        device_registry.async_get_or_create(
            config_entry_id=config_entry_1.entry_id,
            identifiers={("something", "1234")},
            name="name",
            configuration_url=configuration_url,
        )

    update_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        identifiers={("something", "5678")},
        name="name",
    )
    with expectation:
        device_registry.async_update_device(
            update_device.id, configuration_url=configuration_url
        )


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_invalid_configuration_url_from_storage(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading stored devices with an invalid URL."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": ["1234"],
                    "config_subentries": {"1234": [None]},
                    "configuration_url": "invalid",
                    "connections": [],
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": dr.DeviceEntryType.SERVICE,
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "123456ABCDEF"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "2024-02-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": None,
                    "primary_config_entry": "1234",
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)
    assert len(registry.devices) == 1
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.configuration_url == "invalid"


async def test_removing_labels(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we can clear labels."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry = device_registry.async_update_device(entry.id, labels={"label1", "label2"})

    device_registry.async_clear_label_id("label1")
    entry_cleared_label1 = device_registry.async_get_device({("bridgeid", "0123")})

    device_registry.async_clear_label_id("label2")
    entry_cleared_label2 = device_registry.async_get_device({("bridgeid", "0123")})

    assert entry_cleared_label1
    assert entry_cleared_label2
    assert entry != entry_cleared_label1
    assert entry != entry_cleared_label2
    assert entry_cleared_label1 != entry_cleared_label2
    assert entry.labels == {"label1", "label2"}
    assert entry_cleared_label1.labels == {"label2"}
    assert not entry_cleared_label2.labels


async def test_entries_for_label(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test getting device entries by label."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:00")},
        identifiers={("bridgeid", "0000")},
        manufacturer="manufacturer",
        model="model",
    )
    entry_1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:23")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry_1 = device_registry.async_update_device(entry_1.id, labels={"label1"})
    entry_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:56")},
        identifiers={("bridgeid", "0456")},
        manufacturer="manufacturer",
        model="model",
    )
    entry_2 = device_registry.async_update_device(entry_2.id, labels={"label2"})
    entry_1_and_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:89")},
        identifiers={("bridgeid", "0789")},
        manufacturer="manufacturer",
        model="model",
    )
    entry_1_and_2 = device_registry.async_update_device(
        entry_1_and_2.id, labels={"label1", "label2"}
    )

    entries = dr.async_entries_for_label(device_registry, "label1")
    assert len(entries) == 2
    assert entries == [entry_1, entry_1_and_2]

    entries = dr.async_entries_for_label(device_registry, "label2")
    assert len(entries) == 2
    assert entries == [entry_2, entry_1_and_2]

    assert not dr.async_entries_for_label(device_registry, "unknown")
    assert not dr.async_entries_for_label(device_registry, "")


@pytest.mark.parametrize(
    (
        "translation_key",
        "translations",
        "placeholders",
        "expected_device_name",
    ),
    [
        (None, None, None, "Device Bla"),
        (
            "test_device",
            {
                "en": {"component.test.device.test_device.name": "English device"},
            },
            None,
            "English device",
        ),
        (
            "test_device",
            {
                "en": {
                    "component.test.device.test_device.name": "{placeholder} English dev"
                },
            },
            {"placeholder": "special"},
            "special English dev",
        ),
        (
            "test_device",
            {
                "en": {
                    "component.test.device.test_device.name": "English dev {placeholder}"
                },
            },
            {"placeholder": "special"},
            "English dev special",
        ),
    ],
)
async def test_device_name_translation_placeholders(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    translation_key: str | None,
    translations: dict[str, str] | None,
    placeholders: dict[str, str] | None,
    expected_device_name: str | None,
) -> None:
    """Test device name when the device name translation has placeholders."""

    def async_get_cached_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    with patch(
        "homeassistant.helpers.device_registry.translation.async_get_cached_translations",
        side_effect=async_get_cached_translations,
    ):
        entry1 = device_registry.async_get_or_create(
            config_entry_id=config_entry_1.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
            name="Device Bla",
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )
        assert entry1.name == expected_device_name


@pytest.mark.parametrize(
    (
        "translation_key",
        "translations",
        "placeholders",
        "release_channel",
        "expectation",
        "expected_error",
    ),
    [
        (
            "test_device",
            {
                "en": {
                    "component.test.device.test_device.name": "{placeholder} English dev {2ndplaceholder}"
                },
            },
            {"placeholder": "special"},
            ReleaseChannel.STABLE,
            nullcontext(),
            (
                "has translation placeholders '{'placeholder': 'special'}' which do "
                "not match the name '{placeholder} English dev {2ndplaceholder}'"
            ),
        ),
        (
            "test_device",
            {
                "en": {
                    "component.test.device.test_device.name": "{placeholder} English ent {2ndplaceholder}"
                },
            },
            {"placeholder": "special"},
            ReleaseChannel.BETA,
            pytest.raises(
                HomeAssistantError, match="Missing placeholder '2ndplaceholder'"
            ),
            "",
        ),
        (
            "test_device",
            {
                "en": {
                    "component.test.device.test_device.name": "{placeholder} English dev"
                },
            },
            None,
            ReleaseChannel.STABLE,
            nullcontext(),
            (
                "has translation placeholders '{}' which do "
                "not match the name '{placeholder} English dev'"
            ),
        ),
    ],
)
async def test_device_name_translation_placeholders_errors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    translation_key: str | None,
    translations: dict[str, str] | None,
    placeholders: dict[str, str] | None,
    release_channel: ReleaseChannel,
    expectation: AbstractContextManager,
    expected_error: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device name has placeholder issuess."""

    def async_get_cached_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        return translations[language]

    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    with (
        patch(
            "homeassistant.helpers.device_registry.translation.async_get_cached_translations",
            side_effect=async_get_cached_translations,
        ),
        patch(
            "homeassistant.helpers.device_registry.get_release_channel",
            return_value=release_channel,
        ),
        expectation,
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry_1.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
            name="Device Bla",
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )

    assert expected_error in caplog.text


async def test_async_get_or_create_thread_safety(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_get_or_create raises when called from wrong thread."""

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls device_registry.async_update_device from a thread.",
    ):
        await hass.async_add_executor_job(
            partial(
                device_registry.async_get_or_create,
                config_entry_id=mock_config_entry.entry_id,
                connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
                identifiers=set(),
                manufacturer="manufacturer",
                model="model",
            )
        )


async def test_async_remove_device_thread_safety(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_remove_device raises when called from wrong thread."""
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers=set(),
        manufacturer="manufacturer",
        model="model",
    )

    with pytest.raises(
        RuntimeError,
        match="Detected code that calls device_registry.async_remove_device from a thread.",
    ):
        await hass.async_add_executor_job(
            device_registry.async_remove_device, device.id
        )


async def test_device_registry_connections_collision(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test connection collisions in the device registry."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    device1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "none")},
        manufacturer="manufacturer",
        model="model",
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "none")},
        manufacturer="manufacturer",
        model="model",
    )

    assert device1.id == device2.id

    device3 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    # Attempt to merge connection for device3 with the same
    # connection that already exists in device1
    with pytest.raises(
        HomeAssistantError, match=f"Connections.*already registered.*{device1.id}"
    ):
        device_registry.async_update_device(
            device3.id,
            merge_connections={
                (dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE"),
                (dr.CONNECTION_NETWORK_MAC, "none"),
            },
        )

    # Attempt to add new connections for device3 with the same
    # connection that already exists in device1
    with pytest.raises(
        HomeAssistantError, match=f"Connections.*already registered.*{device1.id}"
    ):
        device_registry.async_update_device(
            device3.id,
            new_connections={
                (dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE"),
                (dr.CONNECTION_NETWORK_MAC, "none"),
            },
        )

    device3_refetched = device_registry.async_get(device3.id)
    assert device3_refetched.connections == set()
    assert device3_refetched.identifiers == {("bridgeid", "0123")}

    device1_refetched = device_registry.async_get(device1.id)
    assert device1_refetched.connections == {(dr.CONNECTION_NETWORK_MAC, "none")}
    assert device1_refetched.identifiers == set()

    device2_refetched = device_registry.async_get(device2.id)
    assert device2_refetched.connections == {(dr.CONNECTION_NETWORK_MAC, "none")}
    assert device2_refetched.identifiers == set()

    assert device2_refetched.id == device1_refetched.id
    assert len(device_registry.devices) == 2

    # Attempt to implicitly merge connection for device3 with the same
    # connection that already exists in device1
    device4 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        connections={
            (dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE"),
            (dr.CONNECTION_NETWORK_MAC, "none"),
        },
    )
    assert len(device_registry.devices) == 2
    assert device4.id in (device1.id, device3.id)

    device3_refetched = device_registry.async_get(device3.id)
    device1_refetched = device_registry.async_get(device1.id)
    assert not device1_refetched.connections.isdisjoint(device3_refetched.connections)


async def test_device_registry_identifiers_collision(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test identifiers collisions in the device registry."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    device1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    device2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert device1.id == device2.id

    device3 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    # Attempt to merge identifiers for device3 with the same
    # connection that already exists in device1
    with pytest.raises(
        HomeAssistantError, match=f"Identifiers.*already registered.*{device1.id}"
    ):
        device_registry.async_update_device(
            device3.id, merge_identifiers={("bridgeid", "0123"), ("bridgeid", "8888")}
        )

    # Attempt to add new identifiers for device3 with the same
    # connection that already exists in device1
    with pytest.raises(
        HomeAssistantError, match=f"Identifiers.*already registered.*{device1.id}"
    ):
        device_registry.async_update_device(
            device3.id, new_identifiers={("bridgeid", "0123"), ("bridgeid", "8888")}
        )

    device3_refetched = device_registry.async_get(device3.id)
    assert device3_refetched.connections == set()
    assert device3_refetched.identifiers == {("bridgeid", "4567")}

    device1_refetched = device_registry.async_get(device1.id)
    assert device1_refetched.connections == set()
    assert device1_refetched.identifiers == {("bridgeid", "0123")}

    device2_refetched = device_registry.async_get(device2.id)
    assert device2_refetched.connections == set()
    assert device2_refetched.identifiers == {("bridgeid", "0123")}

    assert device2_refetched.id == device1_refetched.id
    assert len(device_registry.devices) == 2

    # Attempt to implicitly merge identifiers for device3 with the same
    # connection that already exists in device1
    device4 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "4567"), ("bridgeid", "0123")},
    )
    assert len(device_registry.devices) == 2
    assert device4.id in (device1.id, device3.id)

    device3_refetched = device_registry.async_get(device3.id)
    device1_refetched = device_registry.async_get(device1.id)
    assert not device1_refetched.identifiers.isdisjoint(device3_refetched.identifiers)


async def test_primary_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the primary integration field."""
    mock_config_entry_1 = MockConfigEntry(domain="mqtt", title=None)
    mock_config_entry_1.add_to_hass(hass)
    mock_config_entry_2 = MockConfigEntry(title=None)
    mock_config_entry_2.add_to_hass(hass)
    mock_config_entry_3 = MockConfigEntry(title=None)
    mock_config_entry_3.add_to_hass(hass)
    mock_config_entry_4 = MockConfigEntry(domain="matter", title=None)
    mock_config_entry_4.add_to_hass(hass)

    # Create device without model name etc, config entry will not be marked primary
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers=set(),
    )
    assert device.primary_config_entry is None

    # Set model, mqtt config entry will be promoted to primary
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="model",
    )
    assert device.primary_config_entry == mock_config_entry_1.entry_id

    # New config entry with model will be promoted to primary
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="model 2",
    )
    assert device.primary_config_entry == mock_config_entry_2.entry_id

    # New config entry with model will not be promoted to primary
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_3.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="model 3",
    )
    assert device.primary_config_entry == mock_config_entry_2.entry_id

    # New matter config entry with model will not be promoted to primary
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_4.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model="model 3",
    )
    assert device.primary_config_entry == mock_config_entry_2.entry_id

    # Remove the primary config entry
    device = device_registry.async_update_device(
        device.id,
        remove_config_entry_id=mock_config_entry_2.entry_id,
    )
    assert device.primary_config_entry is None

    # Create new
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers=set(),
        manufacturer="manufacturer",
        model="model",
    )
    assert device.primary_config_entry == mock_config_entry_1.entry_id


async def test_update_device_no_connections_or_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test updating a device clearing connections and identifiers."""
    mock_config_entry = MockConfigEntry(domain="mqtt", title=None)
    mock_config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    with pytest.raises(HomeAssistantError):
        device_registry.async_update_device(
            device.id, new_connections=set(), new_identifiers=set()
        )
