"""Tests for the Device Registry."""

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager, nullcontext
from datetime import datetime
from functools import partial
import json
import pathlib
import time
from typing import Any
from unittest.mock import ANY, patch

import attr
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
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_capture_events, flush_store


def _get_device_for_config_entry(
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
    *,
    identifiers: set[tuple[str, str]] | None = None,
    connections: set[tuple[str, str]] | None = None,
) -> dr.DeviceEntry | None:
    """Return the device for a config entry matching identifiers or connections."""
    for device in device_registry.devices.get_entries(identifiers, connections):
        if device.config_entry_id == config_entry_id:
            return device
    return None


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry and add it to hass."""
    entry = MockConfigEntry(title=None)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_config_entry_with_subentries(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry and add it to hass."""
    entry = MockConfigEntry(
        title=None,
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ),
    )
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


@pytest.mark.parametrize("load_registries", [False])
async def test_async_get_before_setup_raises(hass: HomeAssistant) -> None:
    """Test async_get raises when the registry has not been set up."""
    with pytest.raises(RuntimeError, match="Device registry not set up"):
        dr.async_get(hass)

    dr.async_setup(hass)
    assert isinstance(dr.async_get(hass), dr.DeviceRegistry)


async def test_async_load_twice_raises(hass: HomeAssistant) -> None:
    """Test loading the device registry twice raises."""
    registry = dr.async_get(hass)
    with pytest.raises(RuntimeError, match="Device registry is already loaded"):
        await registry.async_load()


async def test_multiple_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test registering a device for multiple config entries with same identifiers."""
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

    # Identifiers and connections are unique per config entry: the two config entries
    # get separate devices, while re-registering for the first entry reuses its device
    assert len(device_registry.devices) == 2
    assert entry.id != entry2.id
    assert entry.id == entry3.id
    assert entry.config_entry_id == config_entry_1.entry_id
    assert entry2.config_entry_id == config_entry_2.entry_id


async def test_multiple_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test re-registering a device under different subentries of one config entry."""
    config_entry = MockConfigEntry(
        subentries_data=(
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        )
    )
    config_entry.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-2",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    # A device belongs to a single subentry; re-registering the same identifiers under
    # another subentry of the same config entry moves the device rather than duplicating
    assert len(device_registry.devices) == 1
    assert entry.id == entry2.id == entry3.id
    assert entry2.config_subentry_id == "mock-subentry-id-2"
    assert entry3.config_subentry_id == "mock-subentry-id-1"


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
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "area_id": "12345A",
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "has_composite_identifiers": False,
                    "connections": [["Zigbee", "23.45.67.89.01"]],
                    "created_at": created_at,
                    "disabled_by": dr.DeviceEntryDisabler.USER,
                    "disabled_by_undefined": False,
                    "id": "bcdefghijklmn",
                    "identifiers": [["serial", "3456ABCDEF12"]],
                    "labels": {"label1", "label2"},
                    "modified_at": modified_at,
                    "name_by_user": "Test Friendly Name",
                    "orphaned_timestamp": None,
                    "domain": None,
                }
            ],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 1

    assert registry.deleted_devices["bcdefghijklmn"] == dr.DeletedDeviceEntry(
        area_id="12345A",
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=None,
        connections={("Zigbee", "23.45.67.89.01")},
        created_at=datetime.fromisoformat(created_at),
        disabled_by=dr.DeviceEntryDisabler.USER,
        id="bcdefghijklmn",
        identifiers={("serial", "3456ABCDEF12")},
        labels={"label1", "label2"},
        modified_at=datetime.fromisoformat(modified_at),
        name_by_user="Test Friendly Name",
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
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=None,
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
        serial_number="serial_no",
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
        area_id="12345A",
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=None,
        connections={("Zigbee", "23.45.67.89.01")},
        created_at=datetime.fromisoformat(created_at),
        disabled_by=dr.DeviceEntryDisabler.USER,
        id="bcdefghijklmn",
        identifiers={("serial", "3456ABCDEF12")},
        labels={"label1", "label2"},
        manufacturer="manufacturer",
        model="model",
        modified_at=utcnow(),
        name_by_user="Test Friendly Name",
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

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"

    deleted_entry = registry.deleted_devices["deletedid"]
    assert deleted_entry.disabled_by is UNDEFINED

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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [
                {
                    "area_id": None,
                    "config_entry_id": "123456",
                    "config_subentry_id": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "disabled_by_undefined": True,
                    "id": "deletedid",
                    "identifiers": [["serial", "123456ABCDFF"]],
                    "labels": [],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "orphaned_timestamp": None,
                    "domain": None,
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

    dr.async_setup(hass)
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
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

    dr.async_setup(hass)
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
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
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
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

    dr.async_setup(hass)
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
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
                    "primary_config_entry": "234567",
                    "name": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
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
                    "primary_config_entry": "234567",
                    "name": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": "234567",
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
async def test_migration_from_1_10(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.10."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 10,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "configuration_url": None,
                    "connections": [["mac", "123456ABCDEF"]],
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
            ],
            "deleted_devices": [
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_entries_subentries": {"234567": [None]},
                    "connections": [["mac", "123456ABCDAB"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "disabled_by_undefined": False,
                    "id": "abcdefghijklm2",
                    "identifiers": [["serial", "123456ABCDAB"]],
                    "labels": [],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "orphaned_timestamp": "1970-01-01T00:00:00+00:00",
                },
            ],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"
    deleted_entry = registry.deleted_devices.get_entry(
        connections=set(),
        identifiers={("serial", "123456ABCDAB")},
    )
    assert deleted_entry.id == "abcdefghijklm2"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
                    "configuration_url": None,
                    "connections": [["mac", "12:34:56:ab:cd:ef"]],
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
            ],
            "deleted_devices": [
                {
                    "area_id": None,
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "domain": None,
                    "connections": [["mac", "12:34:56:ab:cd:ab"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "disabled_by_undefined": False,
                    "id": "abcdefghijklm2",
                    "identifiers": [["serial", "123456ABCDAB"]],
                    "labels": [],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "orphaned_timestamp": "1970-01-01T00:00:00+00:00",
                },
            ],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_11(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.11."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 10,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "configuration_url": None,
                    "connections": [["mac", "123456ABCDEF"]],
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
            ],
            "deleted_devices": [
                {
                    "area_id": None,
                    "config_entries": ["234567"],
                    "config_entries_subentries": {"234567": [None]},
                    "connections": [["mac", "123456ABCDAB"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "id": "abcdefghijklm2",
                    "identifiers": [["serial", "123456ABCDAB"]],
                    "labels": [],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "orphaned_timestamp": "1970-01-01T00:00:00+00:00",
                },
            ],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Test data was loaded
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("serial", "123456ABCDEF")},
    )
    assert entry.id == "abcdefghijklm"
    deleted_entry = registry.deleted_devices.get_entry(
        connections=set(),
        identifiers={("serial", "123456ABCDAB")},
    )
    assert deleted_entry.id == "abcdefghijklm2"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
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
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
                    "configuration_url": None,
                    "connections": [["mac", "12:34:56:ab:cd:ef"]],
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
            ],
            "deleted_devices": [
                {
                    "area_id": None,
                    "config_entry_id": "234567",
                    "config_subentry_id": None,
                    "domain": None,
                    "connections": [["mac", "12:34:56:ab:cd:ab"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "disabled_by_undefined": False,
                    "id": "abcdefghijklm2",
                    "identifiers": [["serial", "123456ABCDAB"]],
                    "labels": [],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "orphaned_timestamp": "1970-01-01T00:00:00+00:00",
                },
            ],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_from_1_12(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from version 1.12.

    Version 3.1 restricts a device to a single config entry and subentry: a device
    belonging to several config entries is split into one device per config entry (each
    keeping a copy of the identifiers/connections and a legacy reference to the composite
    id), while a device in several subentries of one config entry is collapsed onto a
    single subentry (preferring a real subentry over the main entry). A device already
    tied to a single config entry and subentry keeps its id.
    """
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)
    config_entry_3 = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    config_entry_3.add_to_hass(hass)
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                # Composite device belonging to two config entries -> split in two
                {
                    "area_id": "area_1",
                    "config_entries": [
                        mock_config_entry.entry_id,
                        config_entry_2.entry_id,
                    ],
                    "config_entries_subentries": {
                        mock_config_entry.entry_id: [None],
                        config_entry_2.entry_id: [None],
                    },
                    "configuration_url": None,
                    "connections": [["mac", "12:34:56:ab:cd:ef"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "composite0000000000000000000000",
                    "identifiers": [["domain_a", "1"], ["domain_b", "1"]],
                    "labels": ["lab"],
                    "manufacturer": "man",
                    "model": "mod",
                    "name": "composite",
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": "custom name",
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": "SERIAL",
                    "sw_version": None,
                    "via_device_id": None,
                },
                # Composite device spanning several subentries of one config entry ->
                # split into one device per subentry (including the no-subentry one)
                {
                    "area_id": None,
                    "config_entries": [config_entry_3.entry_id],
                    "config_entries_subentries": {
                        config_entry_3.entry_id: [
                            None,
                            "mock-subentry-id-1",
                            "mock-subentry-id-2",
                        ]
                    },
                    "configuration_url": None,
                    "connections": [["mac", "34:56:78:cd:ef:12"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "subentries00000000000000000000",
                    "identifiers": [["domain_c", "1"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": config_entry_3.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
                # Single (config entry, subentry) device -> keeps its id, no legacy ref
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "singleentry00000000000000000000",
                    "identifiers": [["domain_a", "2"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # The single (config entry, subentry) device keeps its id and has no legacy reference
    single = registry.async_get("singleentry00000000000000000000")
    assert single is not None
    assert single.config_entry_id == mock_config_entry.entry_id
    assert single.config_subentry_id is None
    assert single.composite_device_id is None
    assert single.has_composite_identifiers is False

    # The composite spanning two config entries is split into one device per config entry
    assert "composite0000000000000000000000" not in registry.devices
    entry_splits = registry.async_get_devices_for_composite_device_id(
        "composite0000000000000000000000"
    )
    assert len(entry_splits) == 2
    assert {(d.config_entry_id, d.config_subentry_id) for d in entry_splits} == {
        (mock_config_entry.entry_id, None),
        (config_entry_2.entry_id, None),
    }
    for device in entry_splits:
        assert device.id != "composite0000000000000000000000"
        # Each split copies the identity and customizations of the composite ...
        assert device.identifiers == {("domain_a", "1"), ("domain_b", "1")}
        assert device.connections == {("mac", "12:34:56:ab:cd:ef")}
        assert device.area_id == "area_1"
        assert device.name_by_user == "custom name"
        assert device.labels == {"lab"}
        assert device.serial_number == "SERIAL"
        # ... and records its composite_device_id, keeping the copied identifiers
        assert device.composite_device_id == "composite0000000000000000000000"
        assert device.composite_primary_config_entry == mock_config_entry.entry_id
        assert device.split_at is not None
        assert device.has_composite_identifiers is True

    # A device spanning several subentries of ONE config entry is an invalid state (only
    # a buggy 2025.7 subentry migration produced it); it is collapsed to a single device
    # on one subentry - preferring a real subentry over the main entry (None) - rather
    # than split into duplicate devices sharing the same identifiers/connections. It
    # keeps its id and gains no composite bookkeeping.
    assert "subentries00000000000000000000" in registry.devices
    assert (
        registry.async_get_devices_for_composite_device_id(
            "subentries00000000000000000000"
        )
        == []
    )
    collapsed = _get_device_for_config_entry(
        registry, config_entry_3.entry_id, identifiers={("domain_c", "1")}
    )
    assert collapsed is not None
    assert collapsed.id == "subentries00000000000000000000"
    assert collapsed.config_entry_id == config_entry_3.entry_id
    assert collapsed.config_subentry_id == "mock-subentry-id-1"
    assert collapsed.identifiers == {("domain_c", "1")}
    assert collapsed.connections == {("mac", "34:56:78:cd:ef:12")}
    assert collapsed.composite_device_id is None
    assert collapsed.has_composite_identifiers is False


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_backs_up_store_file(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_tmp_config_dir: str,
) -> None:
    """The store file is copied to a timestamped backup before the version 3 migration."""
    hass.config.config_dir = hass_tmp_config_dir
    storage_dir = pathlib.Path(hass_tmp_config_dir) / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    old_store = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {"devices": [], "deleted_devices": []},
    }
    (storage_dir / dr.STORAGE_KEY).write_text(json.dumps(old_store))
    hass_storage[dr.STORAGE_KEY] = old_store

    dr.async_setup(hass)
    await dr.async_load(hass)

    # Exactly one timestamped copy of the pre-migration file was made
    backups = list(storage_dir.glob(f"{dr.STORAGE_KEY}.*.migration_backup"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text()) == old_store
    # The middle segment is a YYYYMMDD_HHMMSS timestamp (strptime raises if malformed)
    datetime.strptime(backups[0].name.split(".")[-2], "%Y%m%d_%H%M%S")


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_detaches_via_device_of_dropped_parent(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A child of an ownerless parent dropped by the migration has its link detached.

    The migration drops an active device with no config entry; normally
    async_remove_device would clear via_device_id links to it, so the migration must too.
    """
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    def _device(**overrides: Any) -> dict[str, Any]:
        device = {
            "area_id": None,
            "config_entries": [entry.entry_id],
            "config_entries_subentries": {entry.entry_id: [None]},
            "configuration_url": None,
            "connections": [],
            "created_at": "1970-01-01T00:00:00+00:00",
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": "device0000000000000000000000000",
            "identifiers": [["test", "1"]],
            "labels": [],
            "manufacturer": None,
            "model": None,
            "name": None,
            "model_id": None,
            "modified_at": "1970-01-01T00:00:00+00:00",
            "name_by_user": None,
            "primary_config_entry": entry.entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": None,
        }
        return device | overrides

    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                # Ownerless parent (no config entries) -> dropped by the migration
                _device(
                    id="orphan0000000000000000000000000",
                    config_entries=[],
                    config_entries_subentries={},
                    identifiers=[["test", "orphan"]],
                    primary_config_entry=None,
                ),
                # Child linked to the orphan via via_device_id
                _device(
                    id="child00000000000000000000000000",
                    identifiers=[["test", "child"]],
                    via_device_id="orphan0000000000000000000000000",
                ),
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # The ownerless parent was dropped; the child survives with its link detached
    assert registry.async_get("orphan0000000000000000000000000") is None
    child = registry.async_get("child00000000000000000000000000")
    assert child is not None
    assert child.via_device_id is None


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_collapses_multi_subentry_device(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A device wrongly assigned to several subentries of one config entry collapses.

    Only a buggy 2025.7 subentry migration produced this state. The migration must
    collapse it to a single device (preferring a real subentry over the main entry,
    None), NOT split it into duplicate devices sharing the same identifiers/connections.
    """
    entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="sub-1",
                subentry_type="test",
                title="Sub 1",
                unique_id="s1",
            ),
        ]
    )
    entry.add_to_hass(hass)
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [entry.entry_id],
                    "config_entries_subentries": {entry.entry_id: [None, "sub-1"]},
                    "configuration_url": None,
                    "connections": [["mac", "12:34:56:ab:cd:ef"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "buggydevice00000000000000000",
                    "identifiers": [["test", "device-1"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Collapsed to a single device (no duplicate), on the real subentry, keeping its id
    assert len(registry.devices) == 1
    device = registry.async_get("buggydevice00000000000000000")
    assert device is not None
    assert device.config_entry_id == entry.entry_id
    assert device.config_subentry_id == "sub-1"
    assert device.config_entries_subentries == {entry.entry_id: {"sub-1"}}
    # It is not split and stays findable by identifier and connection (not shadowed)
    assert (
        registry.async_get_devices_for_composite_device_id(
            "buggydevice00000000000000000"
        )
        == []
    )
    assert device.composite_device_id is None
    assert device.has_composite_identifiers is False
    assert (
        _get_device_for_config_entry(
            registry, entry.entry_id, identifiers={("test", "device-1")}
        )
        is device
    )
    assert (
        _get_device_for_config_entry(
            registry, entry.entry_id, connections={("mac", "12:34:56:ab:cd:ef")}
        )
        is device
    )


async def test_async_get_or_create_moves_device_between_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Re-registering under a different subentry moves the device, not duplicates it.

    Identifiers and connections are unique per config entry (not per subentry), so a
    second async_get_or_create with the same identifier/connection but a different
    subentry of the same config entry moves the existing device - it neither creates a
    duplicate nor raises.
    """
    entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="sub-1",
                subentry_type="test",
                title="1",
                unique_id="s1",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="sub-2",
                subentry_type="test",
                title="2",
                unique_id="s2",
            ),
        ]
    )
    entry.add_to_hass(hass)

    # Same identifier, different subentry -> the existing device is moved
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="sub-1",
        identifiers={("test", "1")},
    )
    assert device.config_subentry_id == "sub-1"
    moved = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="sub-2",
        identifiers={("test", "1")},
    )
    assert moved.id == device.id
    assert moved.config_subentry_id == "sub-2"
    assert len(device_registry.devices) == 1

    # Same connection, different subentry -> also moved, not duplicated
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="sub-1",
        connections={("mac", "12:34:56:ab:cd:ef")},
    )
    moved_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="sub-2",
        connections={("mac", "12:34:56:ab:cd:ef")},
    )
    assert moved_2.id == device_2.id
    assert moved_2.config_subentry_id == "sub-2"
    assert len(device_registry.devices) == 2


async def test_async_get_device_returns_first_match_for_ambiguous_lookup(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Independent devices sharing an identifier resolve to the first match.

    They are not splits of one pre-migration composite (no shared composite_device_id),
    so there is nothing to merge and the lookup returns one of the real devices rather
    than a composite.
    """
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "shared")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "shared")}
    )
    assert device_1.id != device_2.id

    match = device_registry.async_get_device(identifiers={("test", "shared")})
    # A real registry device (the first match), not a synthesized composite
    assert match is device_1
    assert match.id in device_registry.devices
    assert match.config_entries == {entry_1.entry_id}


async def test_async_get_device_prefers_calling_integration(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An ambiguous lookup prefers a device owned by the calling integration."""
    entry_a = MockConfigEntry(domain="itg_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="itg_b")
    entry_b.add_to_hass(hass)
    mac = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
    # itg_a's device is indexed first (created first)
    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, connections={mac}
    )
    device_b = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, connections={mac}
    )
    assert device_a.id != device_b.id

    # Each integration resolves to its own device, regardless of index order
    with patch.object(dr, "_current_integration_domain", return_value="itg_b"):
        assert device_registry.async_get_device(connections={mac}) is device_b
    with patch.object(dr, "_current_integration_domain", return_value="itg_a"):
        assert device_registry.async_get_device(connections={mac}) is device_a

    # A caller owning neither, or no integration frame, falls back to the first match
    with patch.object(dr, "_current_integration_domain", return_value="other"):
        assert device_registry.async_get_device(connections={mac}) is device_a
    with patch.object(dr, "_current_integration_domain", return_value=None):
        assert device_registry.async_get_device(connections={mac}) is device_a


async def test_async_get_device_prefers_matching_domain(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A lookup prefers the device whose config entry domain matches the identifier.

    Right after the migration split, and until identifiers are pruned, every split still
    carries the composite's full identifier set, so a lookup matches all splits; the
    domain match resolves it to the correct single device without a composite.
    """
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "1")}
    )
    # entry_b's device also carries domain_a's identifier (unpruned split state)
    device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id,
        identifiers={("domain_a", "1"), ("domain_b", "2")},
    )
    assert device_registry.async_get_device(identifiers={("domain_a", "1")}) is device_a


async def test_async_remove_device_fans_out_to_migration_composite(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """async_remove_device on a pre-migration composite id removes its splits."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "2")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    device_registry.async_remove_device(old_id)

    assert device_1.id not in device_registry.devices
    assert device_2.id not in device_registry.devices


async def test_async_update_device_fans_out_to_migration_composite(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """async_update_device on a pre-migration composite id fans out to its splits."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "2")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    device_registry.async_update_device(old_id, name_by_user="merged")

    assert device_registry.async_get(device_1.id).name_by_user == "merged"
    assert device_registry.async_get(device_2.id).name_by_user == "merged"


async def test_get_entry_by_connection_without_config_entry_scope(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The container resolves by connection when no config entry scope is given."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    connection = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, connections={connection}
    )
    assert device_registry.devices.get_entry(connections={connection}) is device


async def test_update_unknown_device_id_raises(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Updating an id that is neither a real device nor a composite raises."""
    with pytest.raises(KeyError):
        device_registry.async_update_device("unknown0000000000000000000000ab", name="x")


async def test_cleanup_removes_device_referencing_missing_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Cleanup drops a device still referencing a config entry that no longer exists."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "1")}
    )
    # An entity keeps the device out of the plain-orphan sweep so the defensive
    # missing-config-entry path is reached
    entity_registry.async_get_or_create("sensor", "test", "unique", device_id=device.id)

    # The device's config entry is no longer known to hass
    with patch.object(hass.config_entries, "async_entry_ids", return_value=[]):
        dr.async_cleanup(hass, device_registry, entity_registry)

    assert device.id not in device_registry.devices


async def test_clear_config_entry_removes_device_with_pending_move(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Clearing a config entry removes its device, ignoring a pending move.

    add_config_entry_id records a transient pending move; tearing down the owning config
    entry must remove the device rather than complete that move to the other entry.
    """
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_registry.async_update_device(device.id, add_config_entry_id=entry_2.entry_id)

    device_registry.async_clear_config_entry(entry_1.entry_id)

    assert device.id not in device_registry.devices
    assert device_registry.async_get_device(identifiers={("test", "1")}) is None


async def test_clear_config_entry_clears_pending_move_targeting_it(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Clearing a config entry drops a pending move that targets it.

    A device owned by another entry can hold a transient pending move to the entry being
    removed; clearing it stops a later completion from moving the device onto the removed
    entry instead of deleting it.
    """
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    # Start a deferred move to entry_2 (add_config_entry_id without the paired remove yet)
    device_registry.async_update_device(device.id, add_config_entry_id=entry_2.entry_id)

    # entry_2 is torn down before the move completes
    device_registry.async_clear_config_entry(entry_2.entry_id)

    # Completing the move by removing the owner must delete the device, not move it onto
    # the removed entry_2
    result = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry_1.entry_id
    )
    assert result is None
    assert device.id not in device_registry.devices


async def test_move_to_config_entry_clears_target_entry_deleted_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Moving a device into a config entry clears a matching deleted device it holds.

    A retained-identity move adds no new identifiers/connections, so the deleted device the
    target entry kept for the same identity must still be removed - otherwise the active
    device and the deleted device share the target entry's per-identity slot.
    """
    entry_a = MockConfigEntry()
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry()
    entry_b.add_to_hass(hass)

    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("test", "shared")}
    )
    device_b = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers={("test", "shared")}
    )
    assert device_a.id != device_b.id

    # Leave a deleted device owned by entry_b with the shared identity
    device_registry.async_remove_device(device_b.id)
    assert device_b.id in device_registry.deleted_devices

    # Move device_a into entry_b, retaining its identity
    device_registry.async_update_device(
        device_a.id, new_config_entry_id=entry_b.entry_id
    )

    assert device_registry.async_get(device_a.id).config_entry_id == entry_b.entry_id
    # The deleted device entry_b held for the same identity is cleared, not left immortal
    assert device_b.id not in device_registry.deleted_devices


async def test_get_or_create_via_device_and_via_device_id_raises_cleanly(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Passing both via_device and via_device_id raises without inserting a device."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    with pytest.raises(HomeAssistantError, match="not allowed"):
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("test", "1")},
            via_device=("test", "via"),
            via_device_id="via-device-id",
        )

    assert device_registry.async_get_device(identifiers={("test", "1")}) is None
    assert len(device_registry.devices) == 0


async def test_get_or_create_invalid_subentry_raises_cleanly(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An unknown config_subentry_id raises without inserting a device."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)

    with pytest.raises(HomeAssistantError, match="has no subentry"):
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            config_subentry_id="does-not-exist",
            identifiers={("test", "1")},
        )

    assert device_registry.async_get_device(identifiers={("test", "1")}) is None
    assert len(device_registry.devices) == 0


async def test_add_current_config_entry_is_noop(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Adding the device's current owner records no pending move.

    So a later removal of that sole owner deletes the device instead of moving it to
    itself.
    """
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "1")}
    )

    device_registry.async_update_device(device.id, add_config_entry_id=entry.entry_id)
    result = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry.entry_id
    )

    assert result is None
    assert device.id not in device_registry.devices


@pytest.mark.parametrize(
    "clear_domain",
    ["light", None],
    ids=["explicit-domain", "auto-resolved-domain"],
)
async def test_reregister_restores_orphan(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    clear_domain: str | None,
) -> None:
    """Re-adding an integration restores its orphan.

    async_clear_config_entry records the config entry's domain - passed in by the core
    removal flow, or resolved from the still-present entry when omitted - and a later
    async_get_or_create under the same domain restores that orphan (id, labels, name)
    rather than create a fresh device.
    """
    entry = MockConfigEntry(domain="light")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("light", "1")}, name="Original"
    )
    device_registry.async_update_device(
        device.id, name_by_user="Custom", labels={"label1"}
    )

    # Removing the config entry orphans the deleted device (config_entry_id=None)
    device_registry.async_clear_config_entry(entry.entry_id, clear_domain)
    orphan = device_registry.deleted_devices[device.id]
    assert orphan.config_entry_id is None
    assert orphan.domain == "light"

    # Re-add the integration under a new config entry and re-register the device
    new_entry = MockConfigEntry(domain="light")
    new_entry.add_to_hass(hass)
    restored = device_registry.async_get_or_create(
        config_entry_id=new_entry.entry_id, identifiers={("light", "1")}
    )

    assert restored.id == device.id
    assert restored.config_entry_id == new_entry.entry_id
    assert restored.name_by_user == "Custom"
    assert restored.labels == {"label1"}


async def test_orphan_not_restored_for_other_domain(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An orphan recorded for one integration is not restored by another.

    Identifiers and connections are no longer unique across integrations, so a chance
    collision must not restore another integration's orphaned device onto this one.
    """
    entry = MockConfigEntry(domain="light")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("light", "1")}
    )
    device_registry.async_clear_config_entry(entry.entry_id, entry.domain)
    assert device_registry.deleted_devices[device.id].domain == "light"

    # A different integration registering a device with the same identifiers gets a fresh
    # device, and the orphan is left intact for its own integration to restore later
    other_entry = MockConfigEntry(domain="switch")
    other_entry.add_to_hass(hass)
    fresh = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("light", "1")}
    )
    assert fresh.id != device.id
    assert device.id in device_registry.deleted_devices


async def test_orphaning_replaces_colliding_same_domain_orphan(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Orphaning a device drops a stale same-domain orphan it collides with.

    Two devices from the same integration sharing a connection both orphan under
    config_entry_id=None and would collide in the lookup index; the newest orphan replaces
    the stale one so a re-add restores it deterministically.
    """
    connections = {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")}
    entry_1 = MockConfigEntry(domain="hue")
    entry_1.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        connections=connections,
        identifiers={("hue", "1")},
    )
    entry_2 = MockConfigEntry(domain="hue")
    entry_2.add_to_hass(hass)
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        connections=connections,
        identifiers={("hue", "2")},
    )

    device_registry.async_clear_config_entry(entry_1.entry_id, entry_1.domain)
    assert device_1.id in device_registry.deleted_devices

    device_registry.async_clear_config_entry(entry_2.entry_id, entry_2.domain)
    # The newer orphan replaces the stale one it collides with on the shared connection
    assert device_1.id not in device_registry.deleted_devices
    assert device_2.id in device_registry.deleted_devices

    # Re-adding under the same domain restores the surviving orphan
    entry_3 = MockConfigEntry(domain="hue")
    entry_3.add_to_hass(hass)
    restored = device_registry.async_get_or_create(
        config_entry_id=entry_3.entry_id,
        connections=connections,
        identifiers={("hue", "2")},
    )
    assert restored.id == device_2.id


async def test_orphaned_domain_survives_store_round_trip(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An orphan's recorded domain is written to and read back from storage."""
    entry = MockConfigEntry(domain="hue")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("hue", "1")}
    )
    device_registry.async_clear_config_entry(entry.entry_id, entry.domain)

    registry2 = dr.DeviceRegistry(hass)
    await flush_store(device_registry._store)
    await registry2.async_load()

    assert registry2.deleted_devices[device.id].domain == "hue"


async def test_orphan_keeps_domain_when_config_entry_removed(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An orphan keeps its domain when its config entry is removed via the normal flow.

    config_entries deletes the entry from the registry before calling
    async_clear_config_entry, so async_remove_device can no longer look up the domain and
    records None; the domain passed to async_clear_config_entry is what preserves it on
    the orphan. Without it the orphan would have domain=None and, with the domain-less
    restore fallback gone, could never be restored.
    """
    entry = MockConfigEntry(domain="hue")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("hue", "1")}
    )

    await hass.config_entries.async_remove(entry.entry_id)

    orphan = device_registry.deleted_devices[device.id]
    assert orphan.config_entry_id is None
    assert orphan.domain == "hue"


async def test_cross_domain_orphans_do_not_shadow(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Orphans from different integrations sharing an identifier stay independently found.

    Both orphans would otherwise collide in the config_entry_id=None index; keying orphans
    by their recorded domain keeps each restorable by its own integration.
    """
    shared = {("test", "shared")}
    entry_a = MockConfigEntry(domain="hue")
    entry_a.add_to_hass(hass)
    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers=shared
    )
    entry_b = MockConfigEntry(domain="mqtt")
    entry_b.add_to_hass(hass)
    device_b = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers=shared
    )

    device_registry.async_clear_config_entry(entry_a.entry_id, entry_a.domain)
    device_registry.async_clear_config_entry(entry_b.entry_id, entry_b.domain)

    # Re-adding under each domain restores that domain's own orphan, not the other's
    entry_c = MockConfigEntry(domain="mqtt")
    entry_c.add_to_hass(hass)
    restored_b = device_registry.async_get_or_create(
        config_entry_id=entry_c.entry_id, identifiers=shared
    )
    assert restored_b.id == device_b.id

    entry_d = MockConfigEntry(domain="hue")
    entry_d.add_to_hass(hass)
    restored_a = device_registry.async_get_or_create(
        config_entry_id=entry_d.entry_id, identifiers=shared
    )
    assert restored_a.id == device_a.id


async def test_domainless_orphan_not_restored(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A domain-less orphan is not restored; re-registering creates a fresh device.

    The migration carries orphans over without a domain, which can't be resolved once the
    config entry is gone. Orphans are matched only on their recorded domain, so a
    domain-less one is left for the periodic purge and re-registering makes a new device.
    """
    entry_1 = MockConfigEntry(domain="hue")
    entry_1.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "shared")}
    )

    # Simulate an orphan whose domain can no longer be resolved (the migration carries
    # orphans over without one)
    with patch.object(hass.config_entries, "async_get_entry", return_value=None):
        device_registry.async_clear_config_entry(entry_1.entry_id)
    assert device_registry.deleted_devices[device_1.id].domain is None

    # Re-registering the shared identifier does not restore the domain-less orphan
    entry_2 = MockConfigEntry(domain="hue")
    entry_2.add_to_hass(hass)
    fresh = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "shared")}
    )
    assert fresh.id != device_1.id
    # The un-restored orphan lingers until the periodic purge
    assert device_1.id in device_registry.deleted_devices


async def test_clear_config_subentry_removes_device_with_pending_move(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Clearing a config subentry removes its device, ignoring a pending move.

    add_config_entry_id records a transient pending move; tearing down the owning
    subentry must remove the device rather than complete that move.
    """
    entry_1 = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        config_subentry_id="mock-subentry-id-1",
        identifiers={("test", "1")},
    )
    device_registry.async_update_device(device.id, add_config_entry_id=entry_2.entry_id)

    device_registry.async_clear_config_subentry(entry_1.entry_id, "mock-subentry-id-1")

    assert device.id not in device_registry.devices
    assert device_registry.async_get_device(identifiers={("test", "1")}) is None


async def test_clear_config_subentry_clears_pending_move_targeting_it(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Clearing a config subentry drops a pending move that targets it.

    A device owned by another entry can hold a transient pending move to the subentry being
    removed; clearing it stops a later completion from validating against the removed
    subentry (moving the device onto it, or raising) instead of deleting it.
    """
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry_2.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    # Start a deferred move into entry_2's subentry
    device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry_2.entry_id,
        add_config_subentry_id="mock-subentry-id-1",
    )

    # The target subentry is torn down before the move completes
    device_registry.async_clear_config_subentry(entry_2.entry_id, "mock-subentry-id-1")

    # Completing the move by removing the owner must delete the device, not move it onto
    # the removed subentry
    result = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry_1.entry_id
    )
    assert result is None
    assert device.id not in device_registry.devices


@pytest.mark.parametrize("load_registries", [False])
async def test_async_get_device_composite_reuses_pre_migration_id(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A composite over migration splits reuses the pre-migration device id.

    Backwards compatibility for unmodified integrations: before the rewrite a shared
    connection resolved to one device with a stable id that stored references
    (automations, an entity device_id, a fired event device_id) use. The composite over
    that device's splits reuses the same id, so those references keep resolving; a
    transient id is minted only for a runtime ambiguity between independent devices.
    """
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [entry_a.entry_id, entry_b.entry_id],
                    "config_entries_subentries": {
                        entry_a.entry_id: [None],
                        entry_b.entry_id: [None],
                    },
                    "configuration_url": None,
                    "connections": [["mac", "aa:bb:cc:dd:ee:ff"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "composite00000000000000000000",
                    "identifiers": [["domain_a", "1"], ["domain_b", "2"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": entry_a.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }
    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # A connections-only lookup matches both splits -> composite reuses the old id
    composite = registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}
    )
    assert composite is not None
    assert composite.id == "composite00000000000000000000"
    assert composite.id not in registry.devices
    # It is the same composite async_get resolves for the old id
    assert registry.async_get("composite00000000000000000000").id == composite.id
    # An identifier lookup still domain-resolves to the single owning split (real id)
    resolved = registry.async_get_device(identifiers={("domain_a", "1")})
    assert resolved.id in registry.devices
    assert resolved.config_entry_id == entry_a.entry_id


@pytest.mark.parametrize(
    "update_kwargs",
    [
        pytest.param({"new_identifiers": {("test", "new")}}, id="new_identifiers"),
        pytest.param(
            {"new_connections": {("mac", "12:34:56:ab:cd:ef")}}, id="new_connections"
        ),
        pytest.param(
            {"merge_identifiers": {("test", "extra")}}, id="merge_identifiers"
        ),
        pytest.param(
            {"merge_connections": {("mac", "12:34:56:ab:cd:ef")}},
            id="merge_connections",
        ),
    ],
)
async def test_async_update_device_composite_drops_identity_args(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    update_kwargs: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Identity-rewriting args are ambiguous on a composite: dropped with a warning."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "2")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    # No raise; the arg is ignored with a report-issue warning, devices untouched
    device_registry.async_update_device(old_id, **update_kwargs)
    assert "async_entries_for_config_entry" in caplog.text
    assert "report this issue" in caplog.text
    assert device_registry.async_get(device_1.id).identifiers == {("test", "1")}
    assert device_registry.async_get(device_1.id).connections == set()
    assert device_registry.async_get(device_2.id).identifiers == {("test", "2")}
    assert device_registry.async_get(device_2.id).connections == set()


async def test_async_update_device_composite_drops_only_disallowed_args(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A composite update applies the allowed args and drops the disallowed ones."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "2")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    device_registry.async_update_device(
        old_id,
        new_identifiers={("test", "renamed")},  # disallowed -> dropped
        name_by_user="Custom name",  # allowed -> applied to every underlying device
    )
    assert "new_identifiers" in caplog.text
    # Allowed arg applied to both underlying devices
    assert device_registry.async_get(device_1.id).name_by_user == "Custom name"
    assert device_registry.async_get(device_2.id).name_by_user == "Custom name"
    # Disallowed arg dropped: identities untouched
    assert device_registry.async_get(device_1.id).identifiers == {("test", "1")}
    assert device_registry.async_get(device_2.id).identifiers == {("test", "2")}


async def test_async_update_device_composite_drops_move_args(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """new_config_entry_id / new_config_subentry_id are dropped on the composite path.

    A forwarded move can't be caught by the identifier/connection checks - the splits have
    distinct identities and would move without colliding - so assert each split keeps its
    original (config entry, subentry).
    """
    entry_1 = MockConfigEntry(
        domain="test",
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={}, subentry_type="test", title="Sub", unique_id=None
            )
        ],
    )
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    subentry_id = next(iter(entry_1.subentries))
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "2")}
    )
    old_id = "composite00000000000000000000ab"
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    # Targets are valid, so a forwarded move would land silently - only the owner
    # assertions below catch it.
    device_registry.async_update_device(old_id, new_config_entry_id=entry_2.entry_id)
    device_registry.async_update_device(old_id, new_config_subentry_id=subentry_id)

    assert device_registry.async_get(device_1.id).config_entry_id == entry_1.entry_id
    assert device_registry.async_get(device_1.id).config_subentry_id is None
    assert device_registry.async_get(device_2.id).config_entry_id == entry_2.entry_id


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_drops_device_without_config_entries(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device with no config entry / subentry pairs is dropped during migration."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                # Orphan device with no config entries -> dropped
                {
                    "area_id": None,
                    "config_entries": [],
                    "config_entries_subentries": {},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "orphan00000000000000000000000",
                    "identifiers": [["domain_a", "orphan"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": None,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
                # Normal single-config-entry device -> kept
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "keptdevice0000000000000000000",
                    "identifiers": [["domain_a", "kept"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                },
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # The orphan device was dropped, the normal device kept
    assert registry.async_get("orphan00000000000000000000000") is None
    assert "orphan00000000000000000000000" not in registry.devices
    kept = registry.async_get("keptdevice0000000000000000000")
    assert kept is not None
    assert kept.config_entry_id == mock_config_entry.entry_id
    assert len(registry.devices) == 1


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.usefixtures("freezer")
async def test_migration_splits_deleted_device_with_multiple_config_entries(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A deleted device belonging to several config entries is split, one per entry.

    Each split keeps the identity and customizations so every config entry can still
    restore its share when a matching device is re-registered.
    """
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [],
            "deleted_devices": [
                {
                    "area_id": "area_1",
                    "config_entries": [entry_a.entry_id, entry_b.entry_id],
                    "config_entries_subentries": {
                        entry_a.entry_id: [None],
                        entry_b.entry_id: [None],
                    },
                    "connections": [["mac", "12:34:56:ab:cd:ef"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "disabled_by_undefined": False,
                    "id": "deletedcomposite0000000000000",
                    "identifiers": [["domain_a", "1"]],
                    "labels": ["lab"],
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": "custom name",
                    "orphaned_timestamp": None,
                }
            ],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # Split into one deleted device per config entry, each keeping identity/customizations
    assert len(registry.deleted_devices) == 2
    assert "deletedcomposite0000000000000" not in registry.deleted_devices
    by_entry = {d.config_entry_id: d for d in registry.deleted_devices.values()}
    assert set(by_entry) == {entry_a.entry_id, entry_b.entry_id}
    for deleted in by_entry.values():
        assert deleted.identifiers == {("domain_a", "1")}
        assert deleted.connections == {("mac", "12:34:56:ab:cd:ef")}
        assert deleted.name_by_user == "custom name"
        assert deleted.area_id == "area_1"

    # Each config entry can restore its share, with the customizations preserved
    restored_a = registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "1")}
    )
    assert restored_a.config_entry_id == entry_a.entry_id
    assert restored_a.name_by_user == "custom name"

    restored_b = registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers={("domain_a", "1")}
    )
    assert restored_b.config_entry_id == entry_b.entry_id
    assert restored_b.name_by_user == "custom name"
    assert restored_a.id != restored_b.id


async def test_removing_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test clearing a config entry removes the devices that belong to it."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )

    # Same identifiers on different config entries are separate devices
    assert len(device_registry.devices) == 3
    assert entry.id != entry2.id
    assert entry.id != entry3.id

    device_registry.async_clear_config_entry(config_entry_1.entry_id)

    # Clearing config_entry_1 removes its two devices, leaving config_entry_2's
    assert len(device_registry.devices) == 1
    assert device_registry.async_get(entry.id) is None
    assert device_registry.async_get(entry3.id) is None
    assert device_registry.async_get(entry2.id) is not None


async def test_deleted_device_removing_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test clearing a config entry orphans its deleted devices."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )

    device_registry.async_remove_device(entry.id)
    device_registry.async_remove_device(entry2.id)
    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    device_registry.async_clear_config_entry(config_entry_1.entry_id)

    # Deleted devices are kept but orphaned (config entry cleared) so they can be purged
    assert len(device_registry.deleted_devices) == 2
    assert device_registry.deleted_devices[entry.id].config_entry_id is None
    assert (
        device_registry.deleted_devices[entry2.id].config_entry_id
        == config_entry_2.entry_id
    )

    device_registry.async_clear_config_entry(config_entry_2.entry_id)
    assert len(device_registry.deleted_devices) == 2
    assert device_registry.deleted_devices[entry2.id].config_entry_id is None


async def test_removing_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test clearing a config subentry removes the devices that belong to it."""
    config_entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    config_entry.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-2",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )

    assert len(device_registry.devices) == 2
    assert entry.config_subentry_id == "mock-subentry-id-1"
    assert entry2.config_subentry_id == "mock-subentry-id-2"

    device_registry.async_clear_config_subentry(
        config_entry.entry_id, "mock-subentry-id-1"
    )

    # Only the device on the cleared subentry is removed
    assert len(device_registry.devices) == 1
    assert device_registry.async_get(entry.id) is None
    assert device_registry.async_get(entry2.id) is not None


async def test_deleted_device_removing_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test clearing a config subentry orphans its deleted devices."""
    config_entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    config_entry.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-2",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )

    device_registry.async_remove_device(entry.id)
    device_registry.async_remove_device(entry2.id)
    assert len(device_registry.deleted_devices) == 2

    device_registry.async_clear_config_subentry(
        config_entry.entry_id, "mock-subentry-id-1"
    )

    # Only the deleted device on the cleared subentry is orphaned
    assert len(device_registry.deleted_devices) == 2
    assert device_registry.deleted_devices[entry.id].config_entry_id is None
    assert (
        device_registry.deleted_devices[entry2.id].config_entry_id
        == config_entry.entry_id
    )


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


async def test_removing_area_id_deleted_device(
    device_registry: dr.DeviceRegistry, mock_config_entry: MockConfigEntry
) -> None:
    """Make sure we can clear area id."""
    entry1 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
        identifiers={("bridgeid", "1234")},
        manufacturer="manufacturer",
        model="model",
    )

    entry1_w_area = device_registry.async_update_device(entry1.id, area_id="12345A")
    entry2_w_area = device_registry.async_update_device(entry2.id, area_id="12345B")

    device_registry.async_remove_device(entry1.id)
    device_registry.async_remove_device(entry2.id)

    device_registry.async_clear_area_id("12345A")
    entry1_restored = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry2_restored = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
        identifiers={("bridgeid", "1234")},
    )

    assert not entry1_restored.area_id
    assert entry2_restored.area_id == "12345B"
    assert entry1_w_area != entry1_restored
    assert entry2_w_area != entry2_restored


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


async def test_get_or_create_via_device_and_via_device_id_not_allowed(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Passing both via_device and via_device_id is not allowed."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    via = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "via")}
    )

    with pytest.raises(
        HomeAssistantError,
        match="Passing both `via_device` and `via_device_id` is not allowed",
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("hue", "device")},
            via_device=("hue", "via"),
            via_device_id=via.id,
        )

    # Passing only via_device_id is allowed
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "device")},
        via_device_id=via.id,
    )
    assert device.via_device_id == via.id

    # Passing only the deprecated via_device is still allowed (resolved to via_device_id)
    device_2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "device_2")},
        via_device=("hue", "via"),
    )
    assert device_2.via_device_id == via.id


async def test_get_or_create_via_device_none(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """`via_device=None` means "no via device"; combining it with via_device_id raises."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    via = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "via")}
    )

    # `via_device=None` alongside a via_device_id is contradictory and rejected
    with pytest.raises(
        HomeAssistantError,
        match="Passing both `via_device` and `via_device_id` is not allowed",
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("hue", "device")},
            via_device=None,
            via_device_id=via.id,
        )

    # `via_device=None` on its own means no via device
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "device")},
        via_device=None,
    )
    assert device.via_device_id is None

    # ... and it clears an existing via device on re-registration
    linked = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "linked")},
        via_device_id=via.id,
    )
    assert linked.via_device_id == via.id
    relinked = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "linked")},
        via_device=None,
    )
    assert relinked.id == linked.id
    assert relinked.via_device_id is None


async def test_via_device_prefers_same_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The deprecated via_device resolves to the via device in the same config entry."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    # Two via devices share an identifier, one per config entry
    via_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("hue", "via")}
    )
    via_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("hue", "via")}
    )
    assert via_1.id != via_2.id

    device = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("hue", "device")},
        via_device=("hue", "via"),
    )
    assert device.via_device_id == via_2.id


async def test_via_device_falls_back_to_other_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The deprecated via_device falls back to a via device in another config entry."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    # The via device only exists in entry_1
    via_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("hue", "via")}
    )

    device = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("hue", "device")},
        via_device=("hue", "via"),
    )
    assert device.via_device_id == via_1.id


async def test_via_device_prefers_same_domain(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The deprecated via_device prefers a via device from the same integration.

    When no via device exists in the registering config entry, one from another config
    entry of the same domain is preferred over an arbitrary other-domain match.
    """
    entry = MockConfigEntry(domain="hue")
    entry.add_to_hass(hass)
    other_domain_entry = MockConfigEntry(domain="deconz")
    other_domain_entry.add_to_hass(hass)
    same_domain_entry = MockConfigEntry(domain="hue")
    same_domain_entry.add_to_hass(hass)

    # No via device in `entry`; the other-domain candidate is indexed first
    device_registry.async_get_or_create(
        config_entry_id=other_domain_entry.entry_id, identifiers={("hue", "via")}
    )
    via_same_domain = device_registry.async_get_or_create(
        config_entry_id=same_domain_entry.entry_id, identifiers={("hue", "via")}
    )

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("hue", "device")},
        via_device=("hue", "via"),
    )
    assert device.via_device_id == via_same_domain.id


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

    # config_entry_4's device shares a connection with orig_light3 but belongs to a
    # different config entry, so it is a separate device (identifiers/connections are
    # unique per config entry)
    assert len(device_registry.devices) == 5
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
    assert orig_kitchen_light.area_id == "kitchen"

    orig_kitchen_light_without_suggested_area = device_registry.async_update_device(
        orig_kitchen_light.id, suggested_area=None
    )
    assert orig_kitchen_light_without_suggested_area.area_id == "kitchen"
    assert orig_kitchen_light_without_suggested_area == new_kitchen_light


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
        config_entry_id=mock_config_entry.entry_id,
        config_subentry_id=None,
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
    """Test removing a device's config entry deletes the device."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    assert entry.config_entry_id == config_entry.entry_id

    # Removing the owning config entry with no pending move deletes the device
    updated = device_registry.async_update_device(
        entry.id, remove_config_entry_id=config_entry.entry_id
    )

    assert updated is None
    assert device_registry.async_get(entry.id) is None
    assert len(device_registry.devices) == 0


async def test_update_remove_config_subentries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test removing a device's config subentry deletes the device."""
    config_entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    config_entry.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    assert entry.config_subentry_id == "mock-subentry-id-1"

    # Removing the owning config entry/subentry with no pending move deletes the device
    updated = device_registry.async_update_device(
        entry.id,
        remove_config_entry_id=config_entry.entry_id,
        remove_config_subentry_id="mock-subentry-id-1",
    )

    assert updated is None
    assert device_registry.async_get(entry.id) is None
    assert len(device_registry.devices) == 0


@pytest.mark.parametrize(
    ("initial_area", "device_area_id", "number_of_areas"),
    [
        (None, None, 0),
        ("Living Room", "living_room", 1),
    ],
)
async def test_update_suggested_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    mock_config_entry: MockConfigEntry,
    initial_area: str | None,
    device_area_id: str | None,
    number_of_areas: int,
) -> None:
    """Verify that we can update the suggested area of a device.

    Updating the suggested area of a device should not create a new area, nor should
    it change the area_id of the device.
    """
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bla", "123")},
        suggested_area=initial_area,
    )
    assert entry.area_id == device_area_id

    suggested_area = "Pool"

    with patch.object(device_registry, "async_schedule_save") as mock_save:
        updated_entry = device_registry.async_update_device(
            entry.id, suggested_area=suggested_area
        )

    # Check the device registry was not saved
    assert mock_save.call_count == 0
    assert updated_entry != entry
    assert updated_entry.area_id == device_area_id

    # Check we did not create an area
    pool_area = area_registry.async_get_area_by_name(suggested_area)
    assert pool_area is None
    assert updated_entry.area_id == device_area_id
    assert len(area_registry.areas) == number_of_areas

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }

    # Do not save or fire the event if the suggested
    # area does not result in a change of area
    # but still update the actual entry
    with patch.object(device_registry, "async_schedule_save") as mock_save_2:
        updated_entry = device_registry.async_update_device(
            entry.id, suggested_area="Other"
        )
    assert len(update_events) == 1
    assert mock_save_2.call_count == 0
    assert updated_entry != entry
    assert updated_entry.area_id == device_area_id


@pytest.mark.parametrize(
    "device_disabled_by",
    [
        None,
        dr.DeviceEntryDisabler.CONFIG_ENTRY,
        dr.DeviceEntryDisabler.INTEGRATION,
        dr.DeviceEntryDisabler.USER,
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_update_add_config_entry_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device_disabled_by: dr.DeviceEntryDisabler | None,
) -> None:
    """Check how the disabled_by flag is treated when adding a config entry.

    A device is now owned by a single config entry: add_config_entry_id only records a
    transient pending move (completed by a subsequent remove of the current owner), so on
    its own it leaves the device - including its disabled_by flag - unchanged.
    """
    config_entry_1 = MockConfigEntry(title=None)
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(title=None)
    config_entry_2.add_to_hass(hass)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        config_subentry_id=None,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        disabled_by=device_disabled_by,
    )
    assert entry.disabled_by == device_disabled_by

    entry2 = device_registry.async_update_device(
        entry.id, add_config_entry_id=config_entry_2.entry_id
    )

    # The device is unchanged: still owned by config_entry_1, same disabled_by
    assert entry2.config_entry_id == config_entry_1.entry_id
    assert entry2.config_subentry_id is None
    assert entry2.disabled_by == device_disabled_by

    await hass.async_block_till_done()

    # The pending move is never stored, so no update event is fired
    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }


@pytest.mark.parametrize(
    ("device_disabled_by", "expected_disabled_by"),
    [
        # An enabled device moved onto a disabled entry is disabled by CONFIG_ENTRY
        (None, dr.DeviceEntryDisabler.CONFIG_ENTRY),
        # An existing CONFIG_ENTRY / INTEGRATION / USER disable is preserved
        (dr.DeviceEntryDisabler.CONFIG_ENTRY, dr.DeviceEntryDisabler.CONFIG_ENTRY),
        (dr.DeviceEntryDisabler.INTEGRATION, dr.DeviceEntryDisabler.INTEGRATION),
        (dr.DeviceEntryDisabler.USER, dr.DeviceEntryDisabler.USER),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_update_remove_config_entry_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    device_disabled_by: dr.DeviceEntryDisabler | None,
    expected_disabled_by: dr.DeviceEntryDisabler | None,
) -> None:
    """Check how the disabled_by flag is treated when removing a config entry.

    add_config_entry_id followed by remove_config_entry_id of the current owner moves the
    device to the added config entry. The move re-evaluates disabled_by against the new
    owning entry (like restoring a deleted device): an enabled device moved onto a
    disabled entry becomes CONFIG_ENTRY-disabled, while a USER/INTEGRATION disable - or an
    existing CONFIG_ENTRY disable - is kept.
    """
    config_entry_1 = MockConfigEntry(title=None)
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry(
        title=None, disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    config_entry_2.add_to_hass(hass)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        config_subentry_id=None,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        disabled_by=device_disabled_by,
    )
    assert entry.disabled_by == device_disabled_by

    # add records a pending move, remove of the current owner performs it
    device_registry.async_update_device(
        entry.id, add_config_entry_id=config_entry_2.entry_id
    )
    entry3 = device_registry.async_update_device(
        entry.id, remove_config_entry_id=config_entry_1.entry_id
    )

    # The device moved to config_entry_2, disabled_by reflecting the new entry
    assert entry3 is not None
    assert entry3.config_entry_id == config_entry_2.entry_id
    assert entry3.config_subentry_id is None
    assert entry3.disabled_by == expected_disabled_by

    await hass.async_block_till_done()

    # create + the move update (the add on its own does not fire an event)
    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    expected_changes: dict[str, Any] = {"config_entry_id": config_entry_1.entry_id}
    if expected_disabled_by != device_disabled_by:
        expected_changes["disabled_by"] = device_disabled_by
    assert update_events[1].data == {
        "action": "update",
        "device_id": entry.id,
        "changes": expected_changes,
    }


async def test_move_to_enabled_config_entry_clears_config_entry_disable(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Moving a device to an enabled config entry clears a CONFIG_ENTRY disable.

    The reverse of moving onto a disabled entry; a USER disable is preserved.
    """
    disabled_entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_hass(hass)
    enabled_entry = MockConfigEntry()
    enabled_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id,
        identifiers={("test", "1")},
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )
    device_registry.async_update_device(
        device.id, add_config_entry_id=enabled_entry.entry_id
    )
    moved = device_registry.async_update_device(
        device.id, remove_config_entry_id=disabled_entry.entry_id
    )
    assert moved is not None
    assert moved.config_entry_id == enabled_entry.entry_id
    assert moved.disabled_by is None

    user_device = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id,
        identifiers={("test", "2")},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    device_registry.async_update_device(
        user_device.id, add_config_entry_id=enabled_entry.entry_id
    )
    moved_user = device_registry.async_update_device(
        user_device.id, remove_config_entry_id=disabled_entry.entry_id
    )
    assert moved_user is not None
    assert moved_user.disabled_by is dr.DeviceEntryDisabler.USER


async def test_move_to_config_entry_with_colliding_identity_raises(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Moving a device onto a config entry that already has its identity raises.

    Identifiers and connections are unique per config entry, so a move must validate the
    device's retained identity against the target entry instead of silently overwriting
    the existing device's index slot.
    """
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)

    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "shared")}
    )
    device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "shared")}
    )
    with pytest.raises(dr.DeviceIdentifierCollisionError):
        device_registry.async_update_device(
            device_a.id, new_config_entry_id=entry_2.entry_id
        )

    mac = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
    device_c = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, connections={mac}
    )
    device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, connections={mac}
    )
    with pytest.raises(dr.DeviceConnectionCollisionError):
        device_registry.async_update_device(
            device_c.id, new_config_entry_id=entry_2.entry_id
        )


async def test_add_identifier_keeps_other_config_entry_deleted_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Adding an identifier does not delete a matching deleted device of another entry.

    Deleted devices are per config entry now, so a device in entry A merging an
    identifier must not wipe entry B's deleted-device metadata (its restore data).
    """
    entry_a = MockConfigEntry()
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry()
    entry_b.add_to_hass(hass)

    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("test", "a")}
    )
    device_b = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers={("test", "shared")}
    )
    device_registry.async_update_device(device_b.id, name_by_user="Custom B")
    device_b_id = device_b.id
    device_registry.async_remove_device(device_b.id)

    # entry A's device merges the identifier entry B's deleted device also has
    device_registry.async_update_device(
        device_a.id, merge_identifiers={("test", "shared")}
    )

    # entry B's deleted device survives, so re-registering restores its id and metadata
    restored_b = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers={("test", "shared")}
    )
    assert restored_b.id == device_b_id
    assert restored_b.name_by_user == "Custom B"


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_remaps_via_device_id_to_split(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A child's via_device_id is remapped to a live parent split.

    To the split in the child's own config entry when the parent spanned it, otherwise to
    one of the parent's splits - never left dangling on the removed composite id.
    """
    entry_a = MockConfigEntry(domain="dom_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="dom_b")
    entry_b.add_to_hass(hass)
    entry_c = MockConfigEntry(domain="dom_c")
    entry_c.add_to_hass(hass)

    def _device(id_: str, entries: list[str], identifiers, via: str | None) -> dict:
        return {
            "area_id": None,
            "config_entries": entries,
            "config_entries_subentries": {entry: [None] for entry in entries},
            "configuration_url": None,
            "connections": [],
            "created_at": "1970-01-01T00:00:00+00:00",
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": id_,
            "identifiers": identifiers,
            "labels": [],
            "manufacturer": None,
            "model": None,
            "name": None,
            "model_id": None,
            "modified_at": "1970-01-01T00:00:00+00:00",
            "name_by_user": None,
            "primary_config_entry": entries[0],
            "serial_number": None,
            "sw_version": None,
            "via_device_id": via,
        }

    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                _device(
                    "parent000000000000000000000000",
                    [entry_a.entry_id, entry_b.entry_id],
                    [["dom_a", "p"], ["dom_b", "p"]],
                    None,
                ),
                _device(
                    "child0000000000000000000000000",
                    [entry_a.entry_id],
                    [["dom_a", "c"]],
                    "parent000000000000000000000000",
                ),
                # child in a config entry the parent does not span
                _device(
                    "childc000000000000000000000000",
                    [entry_c.entry_id],
                    [["dom_c", "c"]],
                    "parent000000000000000000000000",
                ),
            ],
            "deleted_devices": [],
        },
    }
    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # The parent splits (fresh split ids, not the old composite id)
    parent_a = registry.async_get_device(identifiers={("dom_a", "p")})
    parent_b = registry.async_get_device(identifiers={("dom_b", "p")})
    assert parent_a is not None
    assert parent_b is not None
    assert parent_a.config_entry_id == entry_a.entry_id
    assert parent_a.id != "parent000000000000000000000000"

    # The child in entry_a points at the parent's entry_a split
    child = registry.async_get_device(identifiers={("dom_a", "c")})
    assert child is not None
    assert child.via_device_id == parent_a.id

    # The child in entry_c, which the parent did not span, points at one of the parent's
    # splits rather than the removed composite id
    child_c = registry.async_get_device(identifiers={("dom_c", "c")})
    assert child_c is not None
    assert child_c.via_device_id in {parent_a.id, parent_b.id}


@pytest.mark.parametrize("load_registries", [False])
@pytest.mark.parametrize(
    ("composite_disabled_by", "expected_split_enabled", "expected_split_disabled"),
    [
        pytest.param(
            None, None, dr.DeviceEntryDisabler.CONFIG_ENTRY, id="enabled_composite"
        ),
        pytest.param(
            dr.DeviceEntryDisabler.USER,
            dr.DeviceEntryDisabler.USER,
            dr.DeviceEntryDisabler.USER,
            id="user_disabled",
        ),
        pytest.param(
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
            None,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
            id="config_entry_disabled",
        ),
    ],
)
async def test_migration_split_disabled_by_follows_config_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    composite_disabled_by: dr.DeviceEntryDisabler | None,
    expected_split_enabled: dr.DeviceEntryDisabler | None,
    expected_split_disabled: dr.DeviceEntryDisabler,
) -> None:
    """A split's disabled_by follows its single owning config entry's disabled state.

    A composite spanning an enabled and a disabled config entry copies its disabled_by to
    both splits; each split is then reconciled against its own entry - the split owned by
    the disabled entry becomes CONFIG_ENTRY disabled (a USER disable is preserved), while
    the split owned by the enabled entry has a stale CONFIG_ENTRY disable cleared.
    """
    entry_enabled = MockConfigEntry(domain="dom_a")
    entry_enabled.add_to_hass(hass)
    entry_disabled = MockConfigEntry(
        domain="dom_b", disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    entry_disabled.add_to_hass(hass)

    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [
                        entry_enabled.entry_id,
                        entry_disabled.entry_id,
                    ],
                    "config_entries_subentries": {
                        entry_enabled.entry_id: [None],
                        entry_disabled.entry_id: [None],
                    },
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": composite_disabled_by,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "composite00000000000000000000",
                    "identifiers": [["dom_a", "x"], ["dom_b", "x"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": entry_enabled.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }
    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    split_enabled = registry.async_get_device(identifiers={("dom_a", "x")})
    split_disabled = registry.async_get_device(identifiers={("dom_b", "x")})
    assert split_enabled is not None
    assert split_disabled is not None
    assert split_enabled.config_entry_id == entry_enabled.entry_id
    assert split_disabled.config_entry_id == entry_disabled.entry_id
    # The split owned by the enabled entry has a stale CONFIG_ENTRY disable cleared
    assert split_enabled.disabled_by is expected_split_enabled
    # The split owned by the disabled entry follows that entry (USER preserved)
    assert split_disabled.disabled_by is expected_split_disabled


@pytest.mark.parametrize("load_registries", [False])
async def test_disabled_by_not_reconciled_without_composite_split(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """disabled_by is reconciled only for split composites, not other migrated devices.

    A 1.12 -> 1.13 migration that splits no composite does not touch a device whose stored
    disabled_by does not match its config entry.
    """
    entry = MockConfigEntry(
        domain="dom_a", disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    entry.add_to_hass(hass)

    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [entry.entry_id],
                    "config_entries_subentries": {entry.entry_id: [None]},
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "device000000000000000000000000",
                    "identifiers": [["dom_a", "x"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }
    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    device = registry.async_get_device(identifiers={("dom_a", "x")})
    assert device is not None
    # The reconcile is gated on a composite split, so disabled_by is left as stored
    assert device.disabled_by is None


@pytest.mark.parametrize("config_entry_disabled", [False, True])
@pytest.mark.parametrize(
    "initial_disabled_by",
    [
        None,
        dr.DeviceEntryDisabler.CONFIG_ENTRY,
        dr.DeviceEntryDisabler.INTEGRATION,
        dr.DeviceEntryDisabler.USER,
    ],
)
async def test_migrate_device_disabled_by_matches_runtime(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    initial_disabled_by: dr.DeviceEntryDisabler | None,
    config_entry_disabled: bool,
) -> None:
    """The migration dict reconcile matches async_config_entry_disabled_by_changed.

    _migrate_device_disabled_by reimplements the runtime helper on stored data, so for
    every combination of device disabled_by and config entry state both must agree.
    """
    config_entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER
        if config_entry_disabled
        else None
    )
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "1")}
    )
    # Explicit disabled_by bypasses async_update_device's own reconciliation
    device_registry.async_update_device(device.id, disabled_by=initial_disabled_by)

    # Runtime helper on the loaded registry
    dr.async_config_entry_disabled_by_changed(device_registry, config_entry)
    runtime_result = device_registry.async_get(device.id).disabled_by

    # Migration helper on the stored representation
    stored = {"disabled_by": initial_disabled_by}
    dr._migrate_device_disabled_by(stored, config_entry_disabled)

    assert stored["disabled_by"] == runtime_result


@pytest.mark.parametrize("load_registries", [False])
async def test_composite_lineage_not_restored_after_remove(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A migrated split loses its composite lineage once removed.

    The deleted device does not carry composite data, so re-registering the split makes a
    plain device that no longer resolves from the pre-migration composite id.
    """
    entry_a = MockConfigEntry(domain="dom_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="dom_b")
    entry_b.add_to_hass(hass)

    old_id = "composite00000000000000000000"
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [entry_a.entry_id, entry_b.entry_id],
                    "config_entries_subentries": {
                        entry_a.entry_id: [None],
                        entry_b.entry_id: [None],
                    },
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": old_id,
                    "identifiers": [["dom_a", "x"], ["dom_b", "x"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": entry_a.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }
    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    split_a = registry.async_get_device(identifiers={("dom_a", "x")})
    assert split_a is not None
    assert split_a.composite_device_id == old_id

    # Remove the split; the deleted device does not carry the composite lineage
    registry.async_remove_device(split_a.id)

    # Re-registering reuses the deleted device's id but drops the composite lineage
    restored = registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("dom_a", "x")}
    )
    assert restored.id == split_a.id
    assert restored.composite_device_id is None
    assert restored not in registry.async_get_devices_for_composite_device_id(old_id)


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
async def test_cleanup_entity_registry_change(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we run a cleanup when entity registry changes.

    Don't pre-load the registries as the debouncer will then not be waiting for
    EVENT_ENTITY_REGISTRY_UPDATED events.
    """
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    dev_reg = dr.async_get(hass)
    ent_reg = er.async_get(hass)

    entry = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

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
        ent_reg.async_get_or_create("light", "hue", "e1", device_id=entry.id)
        await hass.async_block_till_done()
        assert len(mock_call.mock_calls) == 1

        # Removal also triggers
        ent_reg.async_remove(entity.entity_id)
        await hass.async_block_till_done()
        assert len(mock_call.mock_calls) == 2


@pytest.mark.parametrize("initial_area", [None, "12345A"])
@pytest.mark.usefixtures("freezer")
async def test_restore_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry_with_subentries: MockConfigEntry,
    initial_area: str | None,
) -> None:
    """Make sure device id is stable."""
    entry_id = mock_config_entry_with_subentries.entry_id
    subentry_id = "mock-subentry-id-1-1"
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=subentry_id,
        configuration_url="http://config_url_orig.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version_orig",
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer_orig",
        model="model_orig",
        model_id="model_id_orig",
        name="name_orig",
        serial_number="serial_no_orig",
        suggested_area="suggested_area_orig",
        sw_version="version_orig",
        via_device="via_device_id_orig",
    )

    # Apply user customizations
    entry = device_registry.async_update_device(
        entry.id,
        area_id=initial_area,
        disabled_by=dr.DeviceEntryDisabler.USER,
        labels={"label1", "label2"},
        name_by_user="Test Friendly Name",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    # This will create a new device
    entry2 = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry2 == dr.DeviceEntry(
        area_id=None,
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url=None,
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:cd:ef:12")},
        created_at=utcnow(),
        disabled_by=None,
        entry_type=None,
        hw_version=None,
        id=ANY,
        identifiers={("bridgeid", "4567")},
        labels={},
        manufacturer="manufacturer",
        model="model",
        model_id=None,
        modified_at=utcnow(),
        name_by_user=None,
        name=None,
        serial_number=None,
        sw_version=None,
    )
    # This will restore the original device, user customizations of
    # area_id, disabled_by, labels and name_by_user will be restored
    entry3 = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=subentry_id,
        configuration_url="http://config_url_new.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        entry_type=None,
        hw_version="hw_version_new",
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer_new",
        model="model_new",
        model_id="model_id_new",
        name="name_new",
        serial_number="serial_no_new",
        suggested_area="suggested_area_new",
        sw_version="version_new",
        via_device="via_device_id_new",
    )
    assert entry3 == dr.DeviceEntry(
        area_id=initial_area,
        config_entry_id=entry_id,
        config_subentry_id=subentry_id,
        configuration_url="http://config_url_new.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
        created_at=utcnow(),
        disabled_by=dr.DeviceEntryDisabler.USER,
        entry_type=None,
        hw_version="hw_version_new",
        id=entry.id,
        identifiers={("bridgeid", "0123")},
        labels={"label1", "label2"},
        manufacturer="manufacturer_new",
        model="model_new",
        model_id="model_id_new",
        modified_at=utcnow(),
        name_by_user="Test Friendly Name",
        name="name_new",
        serial_number="serial_no_new",
        suggested_area="suggested_area_new",
        sw_version="version_new",
    )

    assert entry.id == entry3.id
    assert entry.id != entry2.id
    assert len(device_registry.devices) == 2
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "update",
        "changes": {
            "area_id": "suggested_area_orig",
            "disabled_by": None,
            "labels": set(),
            "name_by_user": None,
        },
        "device_id": entry.id,
    }
    assert update_events[2].data == {
        "action": "remove",
        "device_id": entry.id,
        "device": entry.dict_repr,
    }
    assert update_events[3].data == {
        "action": "create",
        "device_id": entry2.id,
    }
    assert update_events[4].data == {
        "action": "create",
        "device_id": entry3.id,
    }


@pytest.mark.parametrize(
    ("device_disabled_by", "expected_disabled_by"),
    [
        (None, None),
        (dr.DeviceEntryDisabler.CONFIG_ENTRY, dr.DeviceEntryDisabler.CONFIG_ENTRY),
        (dr.DeviceEntryDisabler.INTEGRATION, dr.DeviceEntryDisabler.INTEGRATION),
        (dr.DeviceEntryDisabler.USER, dr.DeviceEntryDisabler.USER),
        (UNDEFINED, None),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_restore_migrated_device_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    device_disabled_by: dr.DeviceEntryDisabler | UndefinedType | None,
    expected_disabled_by: dr.DeviceEntryDisabler | None,
) -> None:
    """Check how the disabled_by flag is treated when restoring a device."""
    entry_id = mock_config_entry.entry_id
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url="http://config_url_orig.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        disabled_by=None,
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version_orig",
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer_orig",
        model="model_orig",
        model_id="model_id_orig",
        name="name_orig",
        serial_number="serial_no_orig",
        suggested_area="suggested_area_orig",
        sw_version="version_orig",
        via_device="via_device_id_orig",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    deleted_entry = device_registry.deleted_devices[entry.id]
    device_registry.deleted_devices[entry.id] = attr.evolve(
        deleted_entry, disabled_by=UNDEFINED
    )

    # This will restore the original device, user customizations of
    # area_id, disabled_by, labels and name_by_user will be restored
    entry3 = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url="http://config_url_new.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        disabled_by=device_disabled_by,
        entry_type=None,
        hw_version="hw_version_new",
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer_new",
        model="model_new",
        model_id="model_id_new",
        name="name_new",
        serial_number="serial_no_new",
        suggested_area="suggested_area_new",
        sw_version="version_new",
        via_device="via_device_id_new",
    )
    assert entry3 == dr.DeviceEntry(
        area_id="suggested_area_orig",
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url="http://config_url_new.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
        created_at=utcnow(),
        disabled_by=expected_disabled_by,
        entry_type=None,
        hw_version="hw_version_new",
        id=entry.id,
        identifiers={("bridgeid", "0123")},
        labels=set(),
        manufacturer="manufacturer_new",
        model="model_new",
        model_id="model_id_new",
        modified_at=utcnow(),
        name_by_user=None,
        name="name_new",
        serial_number="serial_no_new",
        suggested_area="suggested_area_new",
        sw_version="version_new",
    )

    assert entry.id == entry3.id
    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 3
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "device_id": entry.id,
        "device": entry.dict_repr,
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry3.id,
    }


@pytest.mark.parametrize(
    (
        "config_entry_disabled_by",
        "device_disabled_by_initial",
        "device_disabled_by_restored",
    ),
    [
        (
            None,
            None,
            None,
        ),
        # Config entry not disabled, device was disabled by config entry.
        # Device not disabled when restored.
        (
            None,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
            None,
        ),
        (
            None,
            dr.DeviceEntryDisabler.INTEGRATION,
            dr.DeviceEntryDisabler.INTEGRATION,
        ),
        (
            None,
            dr.DeviceEntryDisabler.USER,
            dr.DeviceEntryDisabler.USER,
        ),
        # Config entry disabled, device not disabled.
        # Device disabled by config entry when restored.
        (
            config_entries.ConfigEntryDisabler.USER,
            None,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
        ),
        (
            config_entries.ConfigEntryDisabler.USER,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
        ),
        (
            config_entries.ConfigEntryDisabler.USER,
            dr.DeviceEntryDisabler.INTEGRATION,
            dr.DeviceEntryDisabler.INTEGRATION,
        ),
        (
            config_entries.ConfigEntryDisabler.USER,
            dr.DeviceEntryDisabler.USER,
            dr.DeviceEntryDisabler.USER,
        ),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_restore_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    config_entry_disabled_by: config_entries.ConfigEntryDisabler | None,
    device_disabled_by_initial: dr.DeviceEntryDisabler | None,
    device_disabled_by_restored: dr.DeviceEntryDisabler | None,
) -> None:
    """Check how the disabled_by flag is treated when restoring a device."""
    entry_id = mock_config_entry.entry_id
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entry_disabled_by
    )
    entry = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url="http://config_url_orig.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        disabled_by=device_disabled_by_initial,
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version_orig",
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer_orig",
        model="model_orig",
        model_id="model_id_orig",
        name="name_orig",
        serial_number="serial_no_orig",
        suggested_area="suggested_area_orig",
        sw_version="version_orig",
        via_device="via_device_id_orig",
    )

    assert entry.disabled_by == device_disabled_by_initial

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    # This will restore the original device, user customizations of
    # area_id, disabled_by, labels and name_by_user will be restored
    entry3 = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url="http://config_url_new.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        disabled_by=None,
        entry_type=None,
        hw_version="hw_version_new",
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer_new",
        model="model_new",
        model_id="model_id_new",
        name="name_new",
        serial_number="serial_no_new",
        suggested_area="suggested_area_new",
        sw_version="version_new",
        via_device="via_device_id_new",
    )
    assert entry3 == dr.DeviceEntry(
        area_id="suggested_area_orig",
        config_entry_id=entry_id,
        config_subentry_id=None,
        configuration_url="http://config_url_new.bla",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
        created_at=utcnow(),
        disabled_by=device_disabled_by_restored,
        entry_type=None,
        hw_version="hw_version_new",
        id=entry.id,
        identifiers={("bridgeid", "0123")},
        labels=set(),
        manufacturer="manufacturer_new",
        model="model_new",
        model_id="model_id_new",
        modified_at=utcnow(),
        name_by_user=None,
        name="name_new",
        serial_number="serial_no_new",
        suggested_area="suggested_area_new",
        sw_version="version_new",
    )

    assert entry.id == entry3.id
    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 3
    assert update_events[0].data == {
        "action": "create",
        "device_id": entry.id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "device_id": entry.id,
        "device": entry.dict_repr,
    }
    assert update_events[2].data == {
        "action": "create",
        "device_id": entry3.id,
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


@pytest.mark.parametrize(
    "field",
    [
        "hw_version",
        "manufacturer",
        "model",
        "model_id",
        "serial_number",
        "sw_version",
    ],
)
@pytest.mark.parametrize(
    ("value", "stored_value", "expected_log"),
    [
        (1.0, "1.0", "passes a non-string value of type float as {field}"),
        ((1, 2), "(1, 2)", "passes a non-string value of type tuple as {field}"),
        ("hw-1", "hw-1", ""),
        (None, None, ""),
    ],
)
async def test_device_info_string_field_validation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    field: str,
    value: Any,
    stored_value: str | None,
    expected_log: str,
) -> None:
    """Test string device info fields are validated and coerced."""
    config_entry_1 = MockConfigEntry()
    config_entry_1.add_to_hass(hass)
    config_entry_2 = MockConfigEntry()
    config_entry_2.add_to_hass(hass)

    entry = device_registry.async_get_or_create(
        config_entry_id=config_entry_1.entry_id,
        identifiers={("something", "1234")},
        name="name",
        **{field: value},
    )
    assert getattr(entry, field) == stored_value

    update_device = device_registry.async_get_or_create(
        config_entry_id=config_entry_2.entry_id,
        identifiers={("something", "5678")},
        name="name",
    )
    updated = device_registry.async_update_device(update_device.id, **{field: value})
    assert updated is not None
    assert getattr(updated, field) == stored_value

    assert expected_log.format(field=field) in caplog.text


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
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "composite_device_id": None,
                    "composite_primary_config_entry": None,
                    "split_at": None,
                    "has_composite_identifiers": False,
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
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
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


async def test_removing_labels_deleted_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Make sure we can clear labels."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    entry1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry1 = device_registry.async_update_device(entry1.id, labels={"label1", "label2"})
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
        identifiers={("bridgeid", "1234")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_update_device(entry2.id, labels={"label3"})

    device_registry.async_remove_device(entry1.id)
    device_registry.async_remove_device(entry2.id)

    device_registry.async_clear_label_id("label1")
    entry1_cleared_label1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    device_registry.async_remove_device(entry1.id)

    device_registry.async_clear_label_id("label2")
    entry1_cleared_label2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    entry2_restored = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:FF")},
        identifiers={("bridgeid", "1234")},
    )

    assert entry1_cleared_label1
    assert entry1_cleared_label2
    assert entry1 != entry1_cleared_label1
    assert entry1 != entry1_cleared_label2
    assert entry1_cleared_label1 != entry1_cleared_label2
    assert entry1.labels == {"label1", "label2"}
    assert entry1_cleared_label1.labels == {"label2"}
    assert not entry1_cleared_label2.labels
    assert entry2 != entry2_restored
    assert entry2_restored.labels == {"label3"}


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
                    "component.test.device.test_device.name": (
                        "{placeholder} English dev"
                    )
                },
            },
            {"placeholder": "special"},
            "special English dev",
        ),
        (
            "test_device",
            {
                "en": {
                    "component.test.device.test_device.name": (
                        "English dev {placeholder}"
                    )
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
                    "component.test.device.test_device.name": (
                        "{placeholder} English dev {2ndplaceholder}"
                    )
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
                    "component.test.device.test_device.name": (
                        "{placeholder} English ent {2ndplaceholder}"
                    )
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
                    "component.test.device.test_device.name": (
                        "{placeholder} English dev"
                    )
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
        match=(
            "Detected code that calls"
            " device_registry._async_update_device"
            " from a thread."
        ),
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
        match=(
            "Detected code that calls"
            " device_registry.async_remove_device"
            " from a thread."
        ),
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


async def test_device_registry_deleted_device_collision(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test update collisions with deleted devices in the device registry."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    device1 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE")},
        manufacturer="manufacturer",
        model="model",
    )
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(device1.id)
    assert len(device_registry.deleted_devices) == 1

    device2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert len(device_registry.deleted_devices) == 1

    device_registry.async_update_device(
        device2.id,
        merge_connections={(dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE")},
    )
    assert len(device_registry.deleted_devices) == 0


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


async def test_connections_validator() -> None:
    """Test checking connections validator."""
    with pytest.raises(ValueError, match="Invalid mac address format"):
        dr.DeviceEntry(
            config_entry_id="mock-config-entry",
            connections={(dr.CONNECTION_NETWORK_MAC, "123456ABCDEF")},
        )


async def test_suggested_area_deprecation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Make sure we do not duplicate entries."""
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

    game_room_area = area_registry.async_get_area_by_name("Game Room")
    assert game_room_area is not None
    assert len(area_registry.areas) == 1

    assert len(device_registry.devices) == 1
    assert entry.area_id == game_room_area.id
    assert entry.suggested_area == "Game Room"

    assert (
        "The deprecated function suggested_area was called. It will be removed in "
        "HA Core 2026.9. Use code which ignores suggested_area instead"
    ) in caplog.text

    device_registry.async_update_device(entry.id, suggested_area="TV Room")

    assert (
        "Detected code that passes a suggested_area to device_registry.async_update "
        "device. This will stop working in Home Assistant 2026.9.0, please report "
        "this issue"
    ) in caplog.text


COMPOSITE_ID = "composite0000000000000000000000"


def _composite_device_storage(
    entry_a: MockConfigEntry, entry_b: MockConfigEntry
) -> dict[str, Any]:
    """Return a v1.10 device registry store with one composite device."""
    return {
        "version": 1,
        "minor_version": 10,
        "data": {
            "devices": [
                {
                    "area_id": "area_1",
                    "config_entries": [entry_a.entry_id, entry_b.entry_id],
                    "config_entries_subentries": {
                        entry_a.entry_id: [None],
                        entry_b.entry_id: [None],
                    },
                    "configuration_url": None,
                    "connections": [["mac", "12:34:56:ab:cd:ef"]],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": COMPOSITE_ID,
                    "identifiers": [["domain_a", "1"], ["domain_b", "1"]],
                    "labels": ["lab"],
                    "manufacturer": "man",
                    "model": "mod",
                    "name": "composite",
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": "custom name",
                    "primary_config_entry": entry_a.entry_id,
                    "serial_number": "SERIAL",
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [],
        },
    }


async def test_single_config_entry_and_compat_properties(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A device has a single config entry; the deprecated shims reflect it."""
    entry = MockConfigEntry(domain="domain_a")
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("domain_a", "1")}
    )

    assert device.config_entry_id == entry.entry_id
    assert device.config_subentry_id is None
    assert device.config_entries == {entry.entry_id}
    assert device.config_entries_subentries == {entry.entry_id: {None}}
    assert device.primary_config_entry == entry.entry_id


async def test_identifiers_unique_per_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The same identifier under two config entries yields two devices."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)

    device_a = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("shared", "1")}
    )
    device_b = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers={("shared", "1")}
    )

    assert device_a.id != device_b.id

    # Scoped lookup returns the owning device
    assert (
        _get_device_for_config_entry(
            device_registry, entry_a.entry_id, identifiers={("shared", "1")}
        ).id
        == device_a.id
    )
    assert (
        _get_device_for_config_entry(
            device_registry, entry_b.entry_id, identifiers={("shared", "1")}
        ).id
        == device_b.id
    )


async def test_collision_only_within_same_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A collision is raised only for two devices of the same config entry."""
    entry = MockConfigEntry(domain="domain_a")
    entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("domain_a", "1")}
    )
    other = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("domain_a", "2")}
    )

    with pytest.raises(dr.DeviceIdentifierCollisionError):
        device_registry.async_update_device(
            other.id, merge_identifiers={("domain_a", "1")}
        )
    assert device_registry.async_get(device.id) is not None


async def test_remove_shadowed_collision_keeps_index_consistent(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Removing a device that shadows a same-entry collision keeps the index consistent.

    allow_collisions lets a device absorb an identifier another device of the same config
    entry holds, shadowing it in the index. When a second config entry also shares that
    identifier, removing the shadowed device then the indexed one must not delete the wrong
    slot or raise KeyError on the mapping the second entry keeps.
    """
    entry_a = MockConfigEntry(domain="test")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="test")
    entry_b.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("test", "1")}
    )
    shadowed = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("test", "2")}
    )
    # The second config entry keeps its own slot for the shared identifier
    other_entry_device = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id, identifiers={("test", "2")}
    )
    # allow_collisions lets `device` absorb the shadowed device's identifier
    device_registry._async_update_device(
        device.id, merge_identifiers={("test", "2")}, allow_collisions=True
    )
    assert device_registry.async_get(device.id).identifiers == {
        ("test", "1"),
        ("test", "2"),
    }
    assert shadowed.id in device_registry.devices

    # Remove the shadowed device, then the indexed one - neither must raise
    device_registry.async_remove_device(shadowed.id)
    device_registry.async_remove_device(device.id)

    # The second config entry's device is still reachable by the shared identifier
    assert (
        device_registry.async_get_device(identifiers={("test", "2")})
        is other_entry_device
    )


@pytest.mark.parametrize(
    ("identity", "merge_kwarg", "merge_extra", "error"),
    [
        pytest.param(
            {"identifiers": {("test", "shared")}},
            "merge_identifiers",
            {("test", "extra")},
            dr.DeviceIdentifierCollisionError,
            id="identifiers",
        ),
        pytest.param(
            {"connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")}},
            "merge_connections",
            {(dr.CONNECTION_NETWORK_MAC, "ab:cd:ef:12:34:56")},
            dr.DeviceConnectionCollisionError,
            id="connections",
        ),
    ],
)
async def test_move_with_merge_validates_retained_identity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    identity: dict[str, set[tuple[str, str]]],
    merge_kwarg: str,
    merge_extra: set[tuple[str, str]],
    error: type[Exception],
) -> None:
    """A move that also merges must validate the retained identity against the target.

    The merged additions are validated, but the retained old identity must be too, or the
    move silently overwrites the target entry's index slot for a device already there.
    """
    entry_a = MockConfigEntry(domain="test")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="test")
    entry_b.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, **identity
    )
    # entry_b already owns a device with the same identity
    device_registry.async_get_or_create(config_entry_id=entry_b.entry_id, **identity)

    # Moving device to entry_b retains its identity, which collides with entry_b's
    # existing device, so the move must raise rather than silently shadow it.
    with pytest.raises(error):
        device_registry.async_update_device(
            device.id,
            new_config_entry_id=entry_b.entry_id,
            **{merge_kwarg: merge_extra},
        )


async def test_move_two_calls_add_then_remove(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test add_config_entry_id records a pending move; the later remove performs it."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "1")}
    )

    # add alone does nothing yet
    device_registry.async_update_device(device.id, add_config_entry_id=entry_b.entry_id)
    assert device_registry.async_get(device.id).config_entry_id == entry_a.entry_id

    # remove of the current owner performs the pending move
    device_registry.async_update_device(
        device.id, remove_config_entry_id=entry_a.entry_id
    )
    moved = device_registry.async_get(device.id)
    assert moved is not None
    assert moved.config_entry_id == entry_b.entry_id


async def test_move_new_config_entry_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test new_config_entry_id moves the device immediately."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "1")}
    )

    device_registry.async_update_device(device.id, new_config_entry_id=entry_b.entry_id)
    assert device_registry.async_get(device.id).config_entry_id == entry_b.entry_id


async def test_move_new_and_add_raises(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test mixing new_config_entry_id with add/remove raises."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "1")}
    )

    with pytest.raises(HomeAssistantError, match="Can't combine"):
        device_registry.async_update_device(
            device.id,
            new_config_entry_id=entry_b.entry_id,
            add_config_entry_id=entry_b.entry_id,
        )


async def test_async_get_or_create_unknown_config_entry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test async_get_or_create raises for an unknown config entry."""
    with pytest.raises(
        HomeAssistantError,
        match="Can't link device to unknown config entry unknown-config-entry",
    ):
        device_registry.async_get_or_create(
            config_entry_id="unknown-config-entry", identifiers={("bridgeid", "0123")}
        )


@pytest.mark.parametrize(
    ("make_update_kwargs", "error_match"),
    [
        pytest.param(
            lambda entry: {"add_config_entry_id": "unknown-config-entry"},
            "Can't link device to unknown config entry unknown-config-entry",
            id="add-unknown-config-entry",
        ),
        pytest.param(
            lambda entry: {"add_config_subentry_id": "mock-subentry-id-2"},
            "Can't add config subentry without specifying config entry",
            id="add-subentry-without-config-entry",
        ),
        pytest.param(
            lambda entry: {
                "add_config_entry_id": entry.entry_id,
                "add_config_subentry_id": "unknown-subentry",
            },
            "has no subentry unknown-subentry",
            id="add-unknown-subentry",
        ),
        pytest.param(
            lambda entry: {"remove_config_subentry_id": "mock-subentry-id-1"},
            "Can't remove config subentry without specifying config entry",
            id="remove-subentry-without-config-entry",
        ),
        pytest.param(
            lambda entry: {"new_config_entry_id": "unknown-config-entry"},
            "Can't move device to unknown config entry unknown-config-entry",
            id="new-unknown-config-entry",
        ),
        pytest.param(
            lambda entry: {"new_config_subentry_id": "unknown-subentry"},
            "has no subentry unknown-subentry",
            id="new-unknown-subentry",
        ),
        pytest.param(
            lambda entry: {
                "new_config_entry_id": entry.entry_id,
                "add_config_entry_id": entry.entry_id,
            },
            "Can't combine new_config_entry_id or new_config_subentry_id",
            id="combine-new-and-add",
        ),
    ],
)
async def test_update_device_config_entry_grammar_errors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    make_update_kwargs: Callable[[MockConfigEntry], dict[str, Any]],
    error_match: str,
) -> None:
    """The config-entry/subentry mutation grammar validates its arguments."""
    entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        identifiers={("bridgeid", "0123")},
    )

    with pytest.raises(HomeAssistantError, match=error_match):
        device_registry.async_update_device(device.id, **make_update_kwargs(entry))


async def test_move_device_to_config_subentry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A device can be moved to another subentry of its config entry.

    Immediately via new_config_subentry_id, or deferred via a pending move
    (add_config_entry_id + add_config_subentry_id, completed by removing the current
    owner). There is no subentry-only deferred move - add_config_subentry_id and
    remove_config_subentry_id without a config entry raise (see
    test_update_device_config_entry_grammar_errors).
    """
    entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        identifiers={("bridgeid", "0123")},
    )

    # new_config_subentry_id moves the device immediately
    moved = device_registry.async_update_device(
        device.id, new_config_subentry_id="mock-subentry-id-2"
    )
    assert moved.config_entry_id == entry.entry_id
    assert moved.config_subentry_id == "mock-subentry-id-2"

    # Deferred move: adding the (same) config entry with the target subentry records a
    # pending move; it does not move the device on its own
    device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry.entry_id,
        add_config_subentry_id="mock-subentry-id-1",
    )
    assert (
        device_registry.async_get(device.id).config_subentry_id == "mock-subentry-id-2"
    )
    # Removing the current owner performs the pending move to the target subentry
    moved_back = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry.entry_id
    )
    assert moved_back is not None
    assert moved_back.config_subentry_id == "mock-subentry-id-1"


async def test_move_device_to_config_entry_and_subentry(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A deferred move can target another config entry and one of its subentries."""
    entry_a = MockConfigEntry()
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-b",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry_b.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("bridgeid", "0123")}
    )

    # The pending move carries the (config entry, subentry) pair
    device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry_b.entry_id,
        add_config_subentry_id="mock-subentry-id-b",
    )
    moved = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry_a.entry_id
    )
    assert moved is not None
    assert moved.config_entry_id == entry_b.entry_id
    assert moved.config_subentry_id == "mock-subentry-id-b"


async def test_pending_move_overwritten_by_later_add(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A later add_config_entry_id / add_config_subentry_id overwrites the pending move."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-2",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry_2.add_to_hass(hass)
    entry_3 = MockConfigEntry()
    entry_3.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("bridgeid", "0123")}
    )

    # Each add records a pending move, overwriting the previous one: first a subentry ...
    device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry_2.entry_id,
        add_config_subentry_id="mock-subentry-id-1",
    )
    # ... a later add to the same entry overwrites just the subentry ...
    device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry_2.entry_id,
        add_config_subentry_id="mock-subentry-id-2",
    )
    # ... a later add to a different entry overwrites the entry (subentry resets to None)
    device_registry.async_update_device(device.id, add_config_entry_id=entry_3.entry_id)

    # None of the adds moved the device
    assert device_registry.async_get(device.id).config_entry_id == entry_1.entry_id

    # Removing the owner performs the last recorded pending move
    moved = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry_1.entry_id
    )
    assert moved is not None
    assert moved.config_entry_id == entry_3.entry_id
    assert moved.config_subentry_id is None


async def test_new_config_entry_id_clears_pending_move(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An immediate new_config_entry_id move clears an earlier pending move.

    Otherwise removing the new owner would perform the stale deferred move instead of
    deleting the device, which has no other config entry.
    """
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    entry_3 = MockConfigEntry()
    entry_3.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("bridgeid", "0123")}
    )

    # Record a pending move to entry_2, then immediately move the device to entry_3
    device_registry.async_update_device(device.id, add_config_entry_id=entry_2.entry_id)
    device_registry.async_update_device(device.id, new_config_entry_id=entry_3.entry_id)
    assert device_registry.async_get(device.id)._pending_move is None

    # Removing the new owner deletes the device rather than performing the stale move
    assert (
        device_registry.async_update_device(
            device.id, remove_config_entry_id=entry_3.entry_id
        )
        is None
    )
    assert device_registry.async_get(device.id) is None


async def test_pending_move_canceled_by_cross_domain_removal(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A removal from a different integration than the one that armed the move cancels it.

    Otherwise an incidental add_config_entry_id (e.g. device_tracker attaching a shared
    MAC) would hijack the owning integration's later cleanup and move the device instead
    of deleting it.
    """
    entry_owner = MockConfigEntry(domain="owner")
    entry_owner.add_to_hass(hass)
    entry_target = MockConfigEntry(domain="attacher")
    entry_target.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_owner.entry_id, identifiers={("test", "1")}
    )

    # The "attacher" integration arms a deferred move to its own entry
    with patch.object(dr, "_current_integration_domain", return_value="attacher"):
        device_registry.async_update_device(
            device.id, add_config_entry_id=entry_target.entry_id
        )
    assert (
        device_registry.async_get(device.id)._pending_move.origin_domain == "attacher"
    )

    # The owning integration later removes its entry - a different domain, so the stale
    # move is canceled and the device is deleted rather than transferred.
    with patch.object(dr, "_current_integration_domain", return_value="owner"):
        result = device_registry.async_update_device(
            device.id, remove_config_entry_id=entry_owner.entry_id
        )
    assert result is None
    assert device_registry.async_get(device.id) is None


async def test_pending_move_completed_by_same_domain_removal(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A removal from the same integration that armed the move completes it."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "1")}
    )

    with patch.object(dr, "_current_integration_domain", return_value="mover"):
        device_registry.async_update_device(
            device.id, add_config_entry_id=entry_2.entry_id
        )
        moved = device_registry.async_update_device(
            device.id, remove_config_entry_id=entry_1.entry_id
        )
    assert moved is not None
    assert moved.config_entry_id == entry_2.entry_id
    assert device_registry.async_get(device.id) is moved


async def test_composite_move_clears_sibling_pending_moves(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Completing one split's move clears the pending move on its composite siblings.

    Arming add_config_entry_id on a composite fans out to every split; once one split
    moves to the target, the others must not also move there and collide.
    """
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    entry_target = MockConfigEntry(domain="test")
    entry_target.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "shared")}
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "shared")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    # Arm a deferred move on the composite id: fans out to both splits
    with patch.object(dr, "_current_integration_domain", return_value="test"):
        device_registry.async_update_device(
            old_id, add_config_entry_id=entry_target.entry_id
        )
    assert device_registry.async_get(device_1.id)._pending_move is not None
    assert device_registry.async_get(device_2.id)._pending_move is not None

    # Complete the move on split 1; split 2's pending move must be cleared
    with patch.object(dr, "_current_integration_domain", return_value="test"):
        device_registry.async_update_device(
            device_1.id, remove_config_entry_id=entry_1.entry_id
        )
    assert (
        device_registry.async_get(device_1.id).config_entry_id == entry_target.entry_id
    )
    assert device_registry.async_get(device_2.id)._pending_move is None

    # Split 2's own removal now deletes it instead of colliding on the shared identifier
    with patch.object(dr, "_current_integration_domain", return_value="test"):
        assert (
            device_registry.async_update_device(
                device_2.id, remove_config_entry_id=entry_2.entry_id
            )
            is None
        )
    assert device_registry.async_get(device_2.id) is None


async def test_add_and_remove_config_entry_in_one_call(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """add_config_entry_id and remove_config_entry_id of the owner move in a single call."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="mock-subentry-id-1",
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            ),
        ]
    )
    entry_2.add_to_hass(hass)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("bridgeid", "0123")}
    )

    # Adding the new entry/subentry and removing the current owner in one call moves at once
    moved = device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry_2.entry_id,
        add_config_subentry_id="mock-subentry-id-1",
        remove_config_entry_id=entry_1.entry_id,
    )
    assert moved is not None
    assert moved.config_entry_id == entry_2.entry_id
    assert moved.config_subentry_id == "mock-subentry-id-1"

    await hass.async_block_till_done()
    assert len(update_events) == 2
    assert update_events[1].data == {
        "action": "update",
        "device_id": device.id,
        "changes": {
            "config_entry_id": entry_1.entry_id,
            "config_subentry_id": None,
        },
    }


async def test_remove_non_owner_config_entry_keeps_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """remove_config_entry_id of a non-owning entry does not perform the pending move."""
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    entry_3 = MockConfigEntry()
    entry_3.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("bridgeid", "0123")}
    )

    # Add a pending move to entry_2, but remove a config entry the device does not own
    result = device_registry.async_update_device(
        device.id,
        add_config_entry_id=entry_2.entry_id,
        remove_config_entry_id=entry_3.entry_id,
    )
    # The device is neither moved nor removed: only removing the owner performs the move
    assert result is not None
    assert result.config_entry_id == entry_1.entry_id

    # The pending move to entry_2 was still recorded; removing the owner now performs it
    moved = device_registry.async_update_device(
        device.id, remove_config_entry_id=entry_1.entry_id
    )
    assert moved is not None
    assert moved.config_entry_id == entry_2.entry_id


@pytest.mark.parametrize("load_registries", [False])
async def test_reregistration_replaces_composite_identifiers(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """First re-registration replaces the copied identifiers with the provided ones."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    hass_storage[dr.STORAGE_KEY] = _composite_device_storage(entry_a, entry_b)

    dr.async_setup(hass)
    await dr.async_load(hass)
    device_registry = dr.async_get(hass)

    split_a = _get_device_for_config_entry(
        device_registry, entry_a.entry_id, identifiers={("domain_a", "1")}
    )
    assert split_a.has_composite_identifiers is True

    reregistered = device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "1")}
    )
    assert reregistered.id == split_a.id
    assert reregistered.identifiers == {("domain_a", "1")}  # domain_b copy pruned
    # assert the copied composite connection is cleared
    assert reregistered.connections == set()
    assert reregistered.has_composite_identifiers is False


@pytest.mark.parametrize("load_registries", [False])
async def test_async_get_returns_restored_composite(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test async_get on the legacy id returns a merged, on-demand composite."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    hass_storage[dr.STORAGE_KEY] = _composite_device_storage(entry_a, entry_b)

    dr.async_setup(hass)
    await dr.async_load(hass)
    device_registry = dr.async_get(hass)

    composite = device_registry.async_get(COMPOSITE_ID)
    assert composite is not None
    assert composite.id == COMPOSITE_ID
    assert composite.config_entries == {entry_a.entry_id, entry_b.entry_id}
    assert composite.config_entries_subentries == {
        entry_a.entry_id: {None},
        entry_b.entry_id: {None},
    }
    assert composite.identifiers == {("domain_a", "1"), ("domain_b", "1")}
    assert composite.serial_number == "SERIAL"

    # Invisible to membership, enumeration and identifier search
    assert COMPOSITE_ID not in device_registry.devices
    assert COMPOSITE_ID not in {d.id for d in device_registry.devices.values()}
    assert (
        device_registry.async_get_device(identifiers={("domain_a", "1")}).id
        != COMPOSITE_ID
    )


@pytest.mark.parametrize("load_registries", [False])
async def test_restored_composite_preserves_primary_config_entry(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The restored composite reports the pre-migration composite's former primary.

    The composite's primary_config_entry is recorded on each split device
    (composite_primary_config_entry) so the restored composite can report it, even when
    it is not the first split.
    """
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    # The composite's primary is entry_b, which is not its first config entry
    storage = _composite_device_storage(entry_a, entry_b)
    storage["data"]["devices"][0]["primary_config_entry"] = entry_b.entry_id
    hass_storage[dr.STORAGE_KEY] = storage

    dr.async_setup(hass)
    await dr.async_load(hass)
    device_registry = dr.async_get(hass)

    composite = device_registry.async_get(COMPOSITE_ID)
    splits = device_registry.async_get_devices_for_composite_device_id(COMPOSITE_ID)

    # The former primary (entry_b) is preserved, even though it is not the first split
    assert composite.primary_config_entry == entry_b.entry_id
    assert composite.primary_config_entry != splits[0].config_entry_id
    # It is a valid member of the merged config entries
    assert composite.primary_config_entry in composite.config_entries


@pytest.mark.parametrize("load_registries", [False])
async def test_clear_config_entry_clears_composite_primary_config_entry(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Clearing the composite's former primary config entry clears the dangling ref."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    # The composite's former primary is entry_a
    hass_storage[dr.STORAGE_KEY] = _composite_device_storage(entry_a, entry_b)

    dr.async_setup(hass)
    await dr.async_load(hass)
    device_registry = dr.async_get(hass)

    split_b = _get_device_for_config_entry(
        device_registry, entry_b.entry_id, identifiers={("domain_a", "1")}
    )
    assert split_b.composite_primary_config_entry == entry_a.entry_id

    # Clearing entry_a removes its split and clears the reference on entry_b's split
    device_registry.async_clear_config_entry(entry_a.entry_id)

    assert (
        _get_device_for_config_entry(
            device_registry, entry_a.entry_id, identifiers={("domain_a", "1")}
        )
        is None
    )
    split_b = _get_device_for_config_entry(
        device_registry, entry_b.entry_id, identifiers={("domain_a", "1")}
    )
    assert split_b is not None
    assert split_b.composite_primary_config_entry is None

    # The restored composite still works, falling back to the remaining split
    composite = device_registry.async_get(COMPOSITE_ID)
    assert composite is not None
    assert composite.primary_config_entry == entry_b.entry_id


@pytest.mark.parametrize("load_registries", [False])
async def test_clear_non_primary_config_entry_keeps_composite_primary_config_entry(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Clearing a non-primary config entry leaves composite_primary_config_entry intact."""
    entry_a = MockConfigEntry(domain="domain_a")
    entry_a.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="domain_b")
    entry_b.add_to_hass(hass)
    # The composite's former primary is entry_a
    hass_storage[dr.STORAGE_KEY] = _composite_device_storage(entry_a, entry_b)

    dr.async_setup(hass)
    await dr.async_load(hass)
    device_registry = dr.async_get(hass)

    # Clearing entry_b (not the former primary) removes its split but keeps the reference
    device_registry.async_clear_config_entry(entry_b.entry_id)

    split_a = _get_device_for_config_entry(
        device_registry, entry_a.entry_id, identifiers={("domain_a", "1")}
    )
    assert split_a is not None
    assert split_a.composite_primary_config_entry == entry_a.entry_id


async def test_dict_repr_dual_writes_deprecated_keys(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test dict_repr exposes both the new and the deprecated compatibility keys."""
    entry = MockConfigEntry(domain="domain_a")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("domain_a", "1")}
    )

    repr_ = device.dict_repr
    assert repr_["config_entry_id"] == entry.entry_id
    assert repr_["config_subentry_id"] is None
    assert repr_["config_entries"] == [entry.entry_id]
    assert repr_["config_entries_subentries"] == {entry.entry_id: [None]}
    assert repr_["primary_config_entry"] == entry.entry_id
    # Internal split-migration fields are not exposed in dict_repr
    assert "composite_device_id" not in repr_
    assert "composite_primary_config_entry" not in repr_
    assert "split_at" not in repr_
    assert "has_composite_identifiers" not in repr_
