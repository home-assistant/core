"""Tests for the Device Registry."""

from collections.abc import Callable, Generator, Iterable
from contextlib import AbstractContextManager, nullcontext
from copy import deepcopy
from datetime import datetime, timedelta
from functools import partial
import json
import pathlib
import time
from typing import Any
from unittest.mock import ANY, AsyncMock, patch

import attr
from freezegun.api import FrozenDateTimeFactory
import pytest
from yarl import URL

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ReleaseChannel
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    frame,
)
from homeassistant.helpers.typing import UNDEFINED, UndefinedType
from homeassistant.util.dt import utcnow

from tests.common import (
    MockConfigEntry,
    MockModule,
    async_capture_events,
    async_fire_time_changed,
    flush_store,
    mock_config_flow,
    mock_device_registry,
    mock_integration,
    mock_platform,
)


@pytest.fixture(autouse=True)
def _downgrade_device_registry_deprecation_reports(
    request: pytest.FixtureRequest,
) -> Generator[None]:
    """Keep the deprecated device registry APIs from raising in tests.

    async_get_device, async_is_composite_device_id, the config entry parameters and
    merge_connections/merge_identifiers parameters of async_update_device, and via_device
    on async_get_or_create are deprecated and raise for core and core integration callers,
    disable them here so we can run tests without triggering deprecation errors.

    Tests which use `mock_integration_frame` will not be affected by this fixture, so
    they can test the deprecation.
    """
    if "mock_integration_frame" in request.fixturenames:
        yield
        return

    def _log_only(what: str, **kwargs: Any) -> None:
        kwargs["core_behavior"] = frame.ReportBehavior.LOG
        kwargs["core_integration_behavior"] = frame.ReportBehavior.LOG
        kwargs["custom_integration_behavior"] = frame.ReportBehavior.LOG
        frame.report_usage(what, **kwargs)

    with patch.object(dr, "report_usage", _log_only):
        yield


def _get_device_for_config_entry(
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
    *,
    identifiers: set[tuple[str, str]] | None = None,
    connections: set[tuple[str, str]] | None = None,
) -> dr.DeviceEntry | None:
    """Return the device for a config entry matching identifiers or connections."""
    for device in device_registry.async_get_devices(
        identifiers=identifiers, connections=connections
    ):
        if device.config_entry_id == config_entry_id:
            return device
    return None


def _mock_deleted_device(
    device_id: str,
    config_entry_id: str,
    identifiers: set[tuple[str, str]],
) -> dr.DeletedDeviceEntry:
    """Create a deleted device entry for seeding stored registry states."""
    return dr.DeletedDeviceEntry(
        area_id=None,
        config_entry_id=config_entry_id,
        config_subentry_id=None,
        connections=set(),
        created_at=utcnow(),
        disabled_by=None,
        id=device_id,
        identifiers=identifiers,
        labels=set(),
        modified_at=utcnow(),
        name_by_user=None,
        orphaned_timestamp=None,
        domain="test",
    )


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
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
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
    # Re-registering under the same subentry is idempotent
    entry2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-1",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    assert entry2.id == entry.id
    assert entry2.config_subentry_id == "mock-subentry-id-1"
    # The idempotent re-registration must not emit the deprecation warning
    assert "A device belongs to one subentry" not in caplog.text

    # A device belongs to a single subentry; re-registering the same identifiers under
    # another subentry of the same config entry is deprecated. For now it warns and moves
    # the existing device (rather than duplicating); from HA Core 2027.8 it will raise.
    entry3 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        config_subentry_id="mock-subentry-id-2",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )
    assert "A device belongs to one subentry" in caplog.text

    # Still one device, now moved to the new subentry
    assert entry3.id == entry.id
    assert len(device_registry.devices) == 1
    assert (
        device_registry.async_get(entry.id).config_subentry_id == "mock-subentry-id-2"
    )


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
            "child_devices": [
                {
                    "area_id": None,
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "created_at": created_at,
                    "disabled_by": "device",
                    "id": "childdeviceid",
                    "identifiers": [["test", "strip_outlet_1"]],
                    "labels": [],
                    "modified_at": modified_at,
                    "name_by_user": None,
                    "name": "Outlet 1",
                    "parent_device_id": "abcdefghijklm",
                }
            ],
            "devices": [
                {
                    "area_id": "12345A",
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
    assert len(registry._deleted_devices) == 1

    # A stored child device is loaded, with disabled_by "device" restored to the enum
    loaded_child = registry.async_get("childdeviceid", include_main_devices=False)
    assert loaded_child is not None
    assert loaded_child.parent_device_id == "abcdefghijklm"
    assert loaded_child.disabled_by is dr.DeviceEntryDisabler.DEVICE
    assert loaded_child.identifiers == {("test", "strip_outlet_1")}

    assert registry._deleted_devices["bcdefghijklmn"] == dr.DeletedDeviceEntry(
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

    deleted_entry = registry._deleted_devices["deletedid"]
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
            "child_devices": [],
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
            "child_devices": [],
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
            "child_devices": [],
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
            "child_devices": [],
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
            "child_devices": [],
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
            "child_devices": [],
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
            "child_devices": [],
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
    deleted_entry = registry._deleted_devices.get_entry(
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
            "child_devices": [],
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
        "minor_version": 11,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [mock_config_entry.entry_id],
                    "config_entries_subentries": {mock_config_entry.entry_id: [None]},
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
                    "config_entries": ["234567"],
                    "config_entries_subentries": {"234567": [None]},
                    "connections": [["mac", "12:34:56:ab:cd:ab"]],
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
    deleted_entry = registry._deleted_devices.get_entry(
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
            "child_devices": [],
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
    assert "composite0000000000000000000000" not in registry._devices
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
    assert "subentries00000000000000000000" in registry._devices
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
async def test_migration_clears_via_device_self_reference(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """The version 3.3 migration clears a device's via_device_id self-reference."""
    entry = MockConfigEntry()
    entry.add_to_hass(hass)
    device_id = "selfref00000000000000000000000"
    hass_storage[dr.STORAGE_KEY] = {
        "version": 3,
        "minor_version": 2,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entry_id": entry.entry_id,
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
                    "id": device_id,
                    "identifiers": [["test", "self"]],
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
                    # Buggy self-reference that the migration must clear
                    "via_device_id": device_id,
                }
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    device = registry.async_get(device_id)
    assert device is not None
    assert device.via_device_id is None


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_clears_composite_via_device_self_reference(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """A self-reference the 3.2 split remapping introduces is cleared.

    A pre-migration composite device linking to itself via via_device_id is split into
    one device per config entry; the 3.2 remapping points each split's stale link at the
    split owning its config entry, i.e. itself. The 3.3 step runs afterwards and clears
    the resulting self-references.
    """
    entry_1 = MockConfigEntry()
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry()
    entry_2.add_to_hass(hass)
    composite_id = "composite000000000000000000000"
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 12,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": [entry_1.entry_id, entry_2.entry_id],
                    "config_entries_subentries": {
                        entry_1.entry_id: [None],
                        entry_2.entry_id: [None],
                    },
                    "configuration_url": None,
                    "connections": [],
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": composite_id,
                    "identifiers": [["test", "composite"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "name": None,
                    "model_id": None,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "primary_config_entry": entry_1.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    # Buggy self-reference remapped to each split by the 3.2 migration
                    "via_device_id": composite_id,
                }
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    splits = registry._devices.get_devices_for_composite_device_id(composite_id)
    assert len(splits) == 2
    assert all(split.via_device_id is None for split in splits)


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


async def test_async_get_or_create_warns_on_subentry_reassignment(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Re-registering under a different subentry warns and moves the device.

    Identifiers and connections are unique per config entry (not per subentry), so a
    second async_get_or_create with the same identifier/connection but a different
    subentry of the same config entry can neither create a duplicate nor keep two
    devices - it moves the existing device to the new subentry. This implicit move is
    deprecated (logs a warning now, will raise in HA Core 2027.8).
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

    # Same identifier, different subentry -> warns and moves the existing device
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
    assert "A device belongs to one subentry" in caplog.text
    assert moved.id == device.id
    assert device_registry.async_get(device.id).config_subentry_id == "sub-2"
    assert len(device_registry.devices) == 1

    # Same connection, different subentry -> also moves
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="sub-1",
        connections={("mac", "12:34:56:ab:cd:ef")},
    )
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        config_subentry_id="sub-2",
        connections={("mac", "12:34:56:ab:cd:ef")},
    )
    assert device_registry.async_get(device_2.id).config_subentry_id == "sub-2"
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
    assert match.id in device_registry._devices
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


@pytest.mark.parametrize(
    ("method", "create_kwargs", "key", "miss_key"),
    [
        pytest.param(
            "async_get_device_by_identifier",
            {"identifiers": {("test", "shared")}},
            ("test", "shared"),
            ("test", "other"),
            id="identifier",
        ),
        pytest.param(
            "async_get_device_by_connection",
            {"connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")}},
            (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef"),
            (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ff"),
            id="connection",
        ),
    ],
)
async def test_async_get_device_scoped_to_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    method: str,
    create_kwargs: dict[str, set[tuple[str, str]]],
    key: tuple[str, str],
    miss_key: tuple[str, str],
) -> None:
    """A single-key lookup scoped to a config entry resolves a shared key uniquely."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, **create_kwargs
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, **create_kwargs
    )
    assert device_1.id != device_2.id

    lookup = getattr(device_registry, method)
    assert lookup(key, entry_1.entry_id) is device_1
    assert lookup(key, entry_2.entry_id) is device_2
    assert lookup(miss_key, entry_1.entry_id) is None
    assert lookup(key, "unknown_entry_id") is None


async def test_async_get_device_by_connection_normalizes(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """MAC connection values are normalized before the scoped lookup."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, "12-34-56-ab-cd-ef"), entry.entry_id
        )
        is device
    )


async def test_async_get_device_id_by_identifier(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """The id lookup returns the device id, and raises when there is no match."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "1")}
    )

    assert (
        dr.async_get_device_id_by_identifier(
            hass, ("test", "1"), config_entry_id=entry.entry_id
        )
        == device.id
    )
    # A missing device is treated as an error: an unknown identifier or the
    # wrong config entry both raise rather than silently returning None.
    with pytest.raises(ValueError, match="no device with identifier"):
        dr.async_get_device_id_by_identifier(
            hass, ("test", "missing"), config_entry_id=entry.entry_id
        )
    with pytest.raises(ValueError, match="no device with identifier"):
        dr.async_get_device_id_by_identifier(
            hass, ("test", "1"), config_entry_id="unknown_entry_id"
        )


@pytest.mark.parametrize(
    ("create_kwargs", "lookup_kwargs", "miss_kwargs"),
    [
        pytest.param(
            {"identifiers": {("test", "shared")}},
            {"identifiers": {("test", "shared")}},
            {"identifiers": {("test", "other")}},
            id="identifier",
        ),
        pytest.param(
            {"connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")}},
            {"connections": {(dr.CONNECTION_NETWORK_MAC, "12-34-56-AB-CD-EF")}},
            {"connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ff")}},
            id="connection",
        ),
    ],
)
async def test_async_get_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    create_kwargs: dict[str, set[tuple[str, str]]],
    lookup_kwargs: dict[str, set[tuple[str, str]]],
    miss_kwargs: dict[str, set[tuple[str, str]]],
) -> None:
    """A plural lookup returns all devices sharing the key across config entries."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, **create_kwargs
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, **create_kwargs
    )
    assert device_1.id != device_2.id

    assert {
        device.id for device in device_registry.async_get_devices(**lookup_kwargs)
    } == {
        device_1.id,
        device_2.id,
    }
    assert device_registry.async_get_devices(**miss_kwargs) == []
    assert [
        device.id
        for device in device_registry.async_get_devices(
            **lookup_kwargs, config_entry_id=entry_1.entry_id
        )
    ] == [device_1.id]
    assert (
        device_registry.async_get_devices(**lookup_kwargs, config_entry_id="unknown")
        == []
    )


async def test_async_get_devices_multiple_keys(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A plural lookup with several keys returns the union of matches, deduplicated."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    mac = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("test", "1")},
        connections={mac},
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "2")}
    )

    devices = device_registry.async_get_devices(
        identifiers={("test", "1"), ("test", "2")}, connections={mac}
    )
    assert {device.id for device in devices} == {device_1.id, device_2.id}
    assert len(devices) == 2


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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    device_registry.async_remove_device(old_id)

    assert device_1.id not in device_registry._devices
    assert device_2.id not in device_registry._devices


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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
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
    assert device_registry._devices.get_entry(connections={connection}) is device


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

    assert device.id not in device_registry._devices


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

    assert device.id not in device_registry._devices
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
    assert device.id not in device_registry._devices


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
    assert device_b.id in device_registry._deleted_devices

    # Move device_a into entry_b, retaining its identity
    device_registry.async_update_device(
        device_a.id, new_config_entry_id=entry_b.entry_id
    )

    assert device_registry.async_get(device_a.id).config_entry_id == entry_b.entry_id
    # The deleted device entry_b held for the same identity is cleared, not left immortal
    assert device_b.id not in device_registry._deleted_devices


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
    assert device.id not in device_registry._devices


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
    orphan = device_registry._deleted_devices[device.id]
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
    assert device_registry._deleted_devices[device.id].domain == "light"

    # A different integration registering a device with the same identifiers gets a fresh
    # device, and the orphan is left intact for its own integration to restore later
    other_entry = MockConfigEntry(domain="switch")
    other_entry.add_to_hass(hass)
    fresh = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("light", "1")}
    )
    assert fresh.id != device.id
    assert device.id in device_registry._deleted_devices


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
    assert device_1.id in device_registry._deleted_devices

    device_registry.async_clear_config_entry(entry_2.entry_id, entry_2.domain)
    # The newer orphan replaces the stale one it collides with on the shared connection
    assert device_1.id not in device_registry._deleted_devices
    assert device_2.id in device_registry._deleted_devices

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

    assert registry2._deleted_devices[device.id].domain == "hue"


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

    orphan = device_registry._deleted_devices[device.id]
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
    assert device_registry._deleted_devices[device_1.id].domain is None

    # Re-registering the shared identifier does not restore the domain-less orphan
    entry_2 = MockConfigEntry(domain="hue")
    entry_2.add_to_hass(hass)
    fresh = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "shared")}
    )
    assert fresh.id != device_1.id
    # The un-restored orphan lingers until the periodic purge
    assert device_1.id in device_registry._deleted_devices


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

    assert device.id not in device_registry._devices
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
    assert device.id not in device_registry._devices


async def test_async_is_composite_device_id(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test asking the registry if a device id is a pre-migration composite id."""
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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    assert device_registry.async_is_composite_device_id(old_id) is True
    assert device_registry.async_is_composite_device_id(device_1.id) is False
    assert device_registry.async_is_composite_device_id(device_2.id) is False
    assert device_registry.async_is_composite_device_id("unknown_id") is None


@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_async_is_composite_device_id_deprecated(
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test async_is_composite_device_id is deprecated.

    It logs for custom integrations and raises for core and core integrations. Use
    async_get with include_composite_devices=False instead.
    """
    what = "calls `device_registry.async_is_composite_device_id`"
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        device_registry.async_is_composite_device_id("some_device_id")

    assert caplog.text.count(what) == expected_log


async def test_async_get_include_composite_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test async_get gates main, child and composite devices independently."""
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
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=entry_1.entry_id,
        identifiers={("test", "child")},
        parent_device_id=device_1.id,
        name="Child",
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    # By default a composite id resolves to the synthesized composite
    composite = device_registry.async_get(old_id)
    assert composite is not None
    assert composite.id == old_id
    assert device_registry.async_get(old_id, include_child_devices=False) == composite

    # include_composite_devices=False resolves a composite id to None, matching
    # `old_id in device_registry._devices`, which is composite-blind
    assert old_id not in device_registry._devices
    assert device_registry.async_get(old_id, include_composite_devices=False) is None
    assert (
        device_registry.async_get(
            old_id, include_child_devices=False, include_composite_devices=False
        )
        is None
    )

    # A registered main device resolves regardless of include_composite_devices
    assert (
        device_registry.async_get(device_1.id, include_composite_devices=False).id
        == device_1.id
    )
    assert (
        device_registry.async_get(
            device_1.id, include_child_devices=False, include_composite_devices=False
        ).id
        == device_1.id
    )

    # An unknown id is None with or without the flag
    assert (
        device_registry.async_get("unknown_id", include_composite_devices=False) is None
    )

    # include_main_devices=False, include_child_devices=False resolves only a composite
    assert (
        device_registry.async_get(
            old_id, include_main_devices=False, include_child_devices=False
        )
        == composite
    )
    # a registered main device, a child device and an unknown id resolve to None
    assert (
        device_registry.async_get(
            device_1.id, include_main_devices=False, include_child_devices=False
        )
        is None
    )
    assert (
        device_registry.async_get(
            child_device.id, include_main_devices=False, include_child_devices=False
        )
        is None
    )
    assert (
        device_registry.async_get(
            "unknown_id", include_main_devices=False, include_child_devices=False
        )
        is None
    )

    # include_main_devices=False, include_composite_devices=False resolves only a child:
    # a composite id resolves to None, a child device still resolves
    assert (
        device_registry.async_get(
            old_id, include_main_devices=False, include_composite_devices=False
        )
        is None
    )
    assert (
        device_registry.async_get(
            child_device.id,
            include_main_devices=False,
            include_composite_devices=False,
        )
        == child_device
    )


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
    assert composite.id not in registry._devices
    # It is the same composite async_get resolves for the old id
    assert registry.async_get("composite00000000000000000000").id == composite.id
    # An identifier lookup still domain-resolves to the single owning split (real id)
    resolved = registry.async_get_device(identifiers={("domain_a", "1")})
    assert resolved.id in registry._devices
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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
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
    assert "orphan00000000000000000000000" not in registry._devices
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
    assert len(registry._deleted_devices) == 2
    assert "deletedcomposite0000000000000" not in registry._deleted_devices
    by_entry = {d.config_entry_id: d for d in registry._deleted_devices.values()}
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
    assert len(device_registry._deleted_devices) == 2

    device_registry.async_clear_config_entry(config_entry_1.entry_id)

    # Deleted devices are kept but orphaned (config entry cleared) so they can be purged
    assert len(device_registry._deleted_devices) == 2
    assert device_registry._deleted_devices[entry.id].config_entry_id is None
    assert (
        device_registry._deleted_devices[entry2.id].config_entry_id
        == config_entry_2.entry_id
    )

    device_registry.async_clear_config_entry(config_entry_2.entry_id)
    assert len(device_registry._deleted_devices) == 2
    assert device_registry._deleted_devices[entry2.id].config_entry_id is None


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
    assert len(device_registry._deleted_devices) == 2

    device_registry.async_clear_config_subentry(
        config_entry.entry_id, "mock-subentry-id-1"
    )

    # Only the deleted device on the cleared subentry is orphaned
    assert len(device_registry._deleted_devices) == 2
    assert device_registry._deleted_devices[entry.id].config_entry_id is None
    assert (
        device_registry._deleted_devices[entry2.id].config_entry_id
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


async def test_get_or_create_unknown_via_device_id_raises_cleanly(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An unknown via_device_id raises without inserting a device."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    removed = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "removed")}
    )
    device_registry.async_remove_device(removed.id)

    with pytest.raises(dr.DeviceInfoError, match="is not a registered device id"):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("hue", "device")},
            via_device_id="unknown-device-id",
        )

    # The id of a removed device is stale and rejected the same way
    with pytest.raises(dr.DeviceInfoError, match="is not a registered device id"):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("hue", "device")},
            via_device_id=removed.id,
        )

    assert device_registry.async_get_device(identifiers={("hue", "device")}) is None
    assert len(device_registry.devices) == 0


async def test_update_device_unknown_via_device_id_raises(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An unknown via_device_id raises on update, leaving the device unchanged."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "device")}
    )

    with pytest.raises(
        HomeAssistantError, match="unknown via device unknown-device-id"
    ):
        device_registry.async_update_device(
            device.id, via_device_id="unknown-device-id"
        )

    assert device_registry.async_get(device.id).via_device_id is None


async def test_update_device_unknown_via_device_id_raises_before_removal(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An unknown via_device_id raises before a removal in the same call."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "device")}
    )

    with pytest.raises(
        HomeAssistantError, match="unknown via device unknown-device-id"
    ):
        device_registry.async_update_device(
            device.id,
            remove_config_entry_id=config_entry.entry_id,
            via_device_id="unknown-device-id",
        )

    # The device was not removed
    assert device_registry.async_get(device.id) == device


async def test_devices_collection_operations(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the supported `Collection[DeviceEntry]` surface of `DeviceRegistry.devices`.

    Iteration yields the entries (not the ids), `len()` returns the count, and
    `DeviceEntry` membership works.
    """
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
    )

    assert list(device_registry.devices) == [entry]
    assert [device.id for device in device_registry.devices] == [entry.id]
    assert len(device_registry.devices) == 1
    assert entry in device_registry.devices


async def test_child_devices_collection_operations(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the supported `Collection[ChildDeviceEntry]` surface of `child_devices`.

    Iteration yields the entries (not the ids), `len()` returns the count, and
    `ChildDeviceEntry` membership works. Unlike `DeviceRegistry.devices`, the child
    collection is a plain read-only view, so mapping-style access, `.values()`, and
    mutation are unavailable.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert list(device_registry.child_devices) == [child_device]
    assert [device.id for device in device_registry.child_devices] == [child_device.id]
    assert len(device_registry.child_devices) == 1
    assert child_device in device_registry.child_devices

    with pytest.raises(TypeError):
        _ = device_registry.child_devices[child_device.id]  # type: ignore[index]
    with pytest.raises(AttributeError):
        device_registry.child_devices.values()  # type: ignore[attr-defined]
    with pytest.raises(TypeError):
        device_registry.child_devices[child_device.id] = child_device  # type: ignore[index]


@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_devices_mapping_access_deprecated(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test mapping-style access to `DeviceRegistry.devices` is deprecated.

    It logs for custom integrations and raises for core and core integrations, while
    iterating the view keeps working for every caller.
    """
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
    )
    what = "uses `device_registry.devices` as a mapping"

    # Iterating the view is the supported API and is never reported.
    assert list(device_registry.devices) == [entry]
    assert caplog.text.count(what) == 0

    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        _ = device_registry.devices[entry.id]

    assert caplog.text.count(what) == expected_log


@pytest.mark.parametrize(
    "integration_frame_path", ["custom_components/test_integration"]
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_devices_membership_by_entry_supported_by_id_deprecated(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test `DeviceEntry` membership is supported while device-id (str) membership warns."""
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
    )
    what = "uses `device_registry.devices` as a mapping"

    # DeviceEntry (value) membership is supported and never reported.
    assert entry in device_registry.devices
    assert caplog.text.count(what) == 0

    # Device-id (str) membership is the deprecated key lookup; it warns here (custom
    # integration).
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()):
        assert entry.id in device_registry.devices
    assert caplog.text.count(what) == 1


@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_deleted_devices_deprecated(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test accessing `DeviceRegistry.deleted_devices` is deprecated.

    It logs for custom integrations and raises for core and core integrations.
    """
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
    )
    device_registry.async_remove_device(entry.id)
    what = "accesses `device_registry.deleted_devices`"

    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        deleted_devices = device_registry.deleted_devices
        # Custom integrations still receive the underlying container.
        assert entry.id in deleted_devices

    assert caplog.text.count(what) == expected_log


@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_async_get_device_deprecated(
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test async_get_device is deprecated.

    It logs for custom integrations and raises for core and core integrations.
    """
    what = "calls `device_registry.async_get_device`"
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        device_registry.async_get_device(identifiers={("some_domain", "some_id")})

    assert caplog.text.count(what) == expected_log


@pytest.mark.parametrize(
    ("parameter", "value", "advice"),
    [
        ("created_at", "2024-01-01T00:00:00+00:00", ", which is ignored"),
        ("default_manufacturer", "manufacturer", "; use `manufacturer` instead"),
        ("default_model", "model", "; use `model` instead"),
        ("default_name", "name", "; use `name` instead"),
        ("modified_at", "2024-01-01T00:00:00+00:00", ", which is ignored"),
        ("via_device", ("some_domain", "via_id"), "; use `via_device_id` instead"),
    ],
)
@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_async_get_or_create_deprecated_parameters(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    parameter: str,
    value: Any,
    advice: str,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test passing deprecated parameters to async_get_or_create.

    They log for custom integrations and raise for core and core integrations.
    """
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("some_domain", "via_id")}
    )

    what = (
        "calls `device_registry.async_get_or_create` with a deprecated "
        f"`{parameter}` parameter{advice}"
    )
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("some_domain", "some_id")},
            **{parameter: value},
        )

    assert caplog.text.count(what) == expected_log


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("created_at", "2024-01-01T00:00:00+00:00"),
        ("default_manufacturer", "manufacturer"),
        ("default_model", "model"),
        ("default_name", "name"),
        ("modified_at", "2024-01-01T00:00:00+00:00"),
        ("via_device", ("some_domain", "via_id")),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_async_get_or_create_deprecated_parameter_reported_before_mutation(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    parameter: str,
    value: Any,
) -> None:
    """A deprecated parameter is reported before the registry is mutated.

    The default frame is a core integration, so the report raises; the new device must
    not be left partially created.
    """
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    with (
        patch.object(frame, "_REPORTED_INTEGRATIONS", set()),
        pytest.raises(RuntimeError),
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("some_domain", "new_device")},
            **{parameter: value},
        )

    # The report raised before insertion, so no partial device was left behind.
    assert (
        device_registry.async_get_device_by_identifier(
            ("some_domain", "new_device"), config_entry.entry_id
        )
        is None
    )


async def test_async_get_or_create_unexpected_keyword_argument(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test passing an unexpected keyword argument to async_get_or_create raises."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)

    with pytest.raises(
        TypeError,
        match="got unexpected keyword arguments 'unexpected'",
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("some_domain", "some_id")},
            unexpected="value",
        )


@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_async_update_device_config_entry_params_deprecated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test the config entry params of async_update_device are deprecated.

    Passing any of add_config_entry_id, add_config_subentry_id, remove_config_entry_id
    or remove_config_subentry_id logs for custom integrations, and raises for core and
    core integrations.
    """
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("some_domain", "some_id")}
    )

    what = "calls `device_registry.async_update_device` with one of"
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        device_registry.async_update_device(
            device.id, remove_config_entry_id=config_entry.entry_id
        )

    assert caplog.text.count(what) == expected_log


@pytest.mark.parametrize(
    "update_kwargs",
    [
        pytest.param(
            {"merge_connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")}},
            id="merge_connections",
        ),
        pytest.param(
            {"merge_identifiers": {("some_domain", "extra")}}, id="merge_identifiers"
        ),
    ],
)
@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(RuntimeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(RuntimeError),
            1,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_async_update_device_merge_params_deprecated(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    update_kwargs: dict[str, set[tuple[str, str]]],
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test merge_connections/merge_identifiers of async_update_device are deprecated.

    Passing either logs for custom integrations, and raises for core and core
    integrations. The parameters stay available on the protected _async_update_device
    for internal use by the registry.
    """
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("some_domain", "some_id")}
    )

    what = "calls `device_registry.async_update_device` with `merge_connections`"
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        device_registry.async_update_device(device.id, **update_kwargs)

    assert caplog.text.count(what) == expected_log


async def test_get_or_create_via_device_self_reference_ignored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device referencing itself via the deprecated via_device is ignored and logged."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "self")}
    )

    updated = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("hue", "self")},
        via_device=("hue", "self"),
    )

    assert updated.id == device.id
    assert updated.via_device_id is None
    assert (
        "calls `device_registry.async_get_or_create` with a `via_device` "
        "referencing the device itself" in caplog.text
    )


async def test_get_or_create_via_device_id_self_reference_raises(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A device referencing itself via via_device_id raises, leaving it unchanged."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "self")}
    )

    with pytest.raises(
        HomeAssistantError, match="A device can not be its own via device"
    ):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("hue", "self")},
            via_device_id=device.id,
        )

    assert device_registry.async_get(device.id).via_device_id is None


async def test_update_device_via_device_id_self_reference_raises(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Updating a device to reference itself via via_device_id raises."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "self")}
    )

    with pytest.raises(
        HomeAssistantError, match="A device can not be its own via device"
    ):
        device_registry.async_update_device(device.id, via_device_id=device.id)

    assert device_registry.async_get(device.id).via_device_id is None


async def test_update_device_via_device_id_self_reference_raises_before_removal(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A self-referencing via_device_id raises before a removal in the same call."""
    config_entry = MockConfigEntry()
    config_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("hue", "device")}
    )

    with pytest.raises(
        HomeAssistantError, match="A device can not be its own via device"
    ):
        device_registry.async_update_device(
            device.id,
            remove_config_entry_id=config_entry.entry_id,
            via_device_id=device.id,
        )

    # The device was not removed
    assert device_registry.async_get(device.id) == device


async def test_update_device_composite_via_device_id_self_reference_raises_before_removal(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A composite via_device_id self-reference raises before a removal in one call."""
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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    # old_id resolves to device_1 (the split owned by entry_1), so linking device_1 to
    # it is a self-reference; it must raise before the removal deletes the device.
    with pytest.raises(
        HomeAssistantError, match="A device can not be its own via device"
    ):
        device_registry.async_update_device(
            device_1.id,
            remove_config_entry_id=entry_1.entry_id,
            via_device_id=old_id,
        )

    assert device_1.id in device_registry._devices


async def test_get_or_create_composite_via_device_id_resolved(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A composite via_device_id resolves to a split: same entry, same domain, any."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="matter")
    entry_2.add_to_hass(hass)
    entry_3 = MockConfigEntry(domain="matter")
    entry_3.add_to_hass(hass)
    entry_4 = MockConfigEntry(domain="other")
    entry_4.add_to_hass(hass)
    split_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "hub")}
    )
    split_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "hub")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry._devices[split_1.id] = attr.evolve(
        split_1, composite_device_id=old_id
    )
    device_registry._devices[split_2.id] = attr.evolve(
        split_2, composite_device_id=old_id
    )

    # A child in a config entry owning a split resolves to that split
    child = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("matter", "child")},
        via_device_id=old_id,
    )
    assert child.via_device_id == split_2.id
    assert "passes the id of a pre-migration composite device" in caplog.text

    # A child in another config entry of a split's domain resolves to that split
    domain_child = device_registry.async_get_or_create(
        config_entry_id=entry_3.entry_id,
        identifiers={("matter", "child")},
        via_device_id=old_id,
    )
    assert domain_child.via_device_id == split_2.id

    # A child sharing neither config entry nor domain falls back to any split
    other_child = device_registry.async_get_or_create(
        config_entry_id=entry_4.entry_id,
        identifiers={("other", "child")},
        via_device_id=old_id,
    )
    assert other_child.via_device_id == split_1.id


async def test_update_device_composite_via_device_id_resolved(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A composite via_device_id resolves to a split on update."""
    entry_1 = MockConfigEntry(domain="test")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="test")
    entry_2.add_to_hass(hass)
    split_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id, identifiers={("test", "hub")}
    )
    split_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "hub")}
    )
    old_id = "composite00000000000000000000ab"
    # Simulate a migration split: both devices carry the pre-migration composite id
    device_registry._devices[split_1.id] = attr.evolve(
        split_1, composite_device_id=old_id
    )
    device_registry._devices[split_2.id] = attr.evolve(
        split_2, composite_device_id=old_id
    )
    child = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id, identifiers={("test", "child")}
    )

    updated = device_registry.async_update_device(child.id, via_device_id=old_id)

    assert updated.via_device_id == split_2.id
    assert "passes the id of a pre-migration composite device" in caplog.text


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
    assert len(device_registry._deleted_devices) == 1

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
    assert list(device_registry._devices) == list(registry2._devices)
    assert list(device_registry._deleted_devices) == list(registry2._deleted_devices)

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
    via_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("hue", "via")},
    )
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
            via_device_id=via_device.id,
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
        via_device_id=via_device.id,
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
    ("config_entry_disabled_by", "device_disabled_by"),
    [
        (None, None),
        (
            config_entries.ConfigEntryDisabler.USER,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
        ),
        (None, dr.DeviceEntryDisabler.INTEGRATION),
        (None, dr.DeviceEntryDisabler.USER),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_update_add_config_entry_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_disabled_by: config_entries.ConfigEntryDisabler | None,
    device_disabled_by: dr.DeviceEntryDisabler | None,
) -> None:
    """Check how the disabled_by flag is treated when adding a config entry.

    A device is now owned by a single config entry: add_config_entry_id only records a
    transient pending move (completed by a subsequent remove of the current owner), so on
    its own it leaves the device - including its disabled_by flag - unchanged.
    """
    config_entry_1 = MockConfigEntry(title=None, disabled_by=config_entry_disabled_by)
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
    ("config_entry_disabled_by", "device_disabled_by", "expected_disabled_by"),
    [
        # An enabled device moved onto a disabled entry is disabled by CONFIG_ENTRY
        (None, None, dr.DeviceEntryDisabler.CONFIG_ENTRY),
        # An existing CONFIG_ENTRY / INTEGRATION / USER disable is preserved
        (
            config_entries.ConfigEntryDisabler.USER,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
            dr.DeviceEntryDisabler.CONFIG_ENTRY,
        ),
        (None, dr.DeviceEntryDisabler.INTEGRATION, dr.DeviceEntryDisabler.INTEGRATION),
        (None, dr.DeviceEntryDisabler.USER, dr.DeviceEntryDisabler.USER),
    ],
)
@pytest.mark.usefixtures("freezer")
async def test_update_remove_config_entry_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_disabled_by: config_entries.ConfigEntryDisabler | None,
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
    config_entry_1 = MockConfigEntry(title=None, disabled_by=config_entry_disabled_by)
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


async def test_move_with_conflicting_disabled_by_ignored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An explicit disabled_by contradicting the target entry's disabled state.

    The conflicting disabled_by is ignored, the disabled state is updated to
    reflect the new config entry's disabled state, and a deprecation warning is
    logged. This will raise in HA Core 2027.8.
    """
    disabled_entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_hass(hass)
    enabled_entry = MockConfigEntry()
    enabled_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id, identifiers={("test", "1")}
    )
    moved = device_registry.async_update_device(
        device.id,
        disabled_by=None,
        new_config_entry_id=disabled_entry.entry_id,
    )
    assert moved is not None
    assert moved.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert (
        "Detected code that sets disabled_by to None when moving a device to the "
        f"disabled config entry {disabled_entry.entry_id}. This will stop working "
        "in Home Assistant 2027.8, please report this issue"
    ) in caplog.text

    disabled_device = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id,
        identifiers={("test", "2")},
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )
    moved_disabled = device_registry.async_update_device(
        disabled_device.id,
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
        new_config_entry_id=enabled_entry.entry_id,
    )
    assert moved_disabled is not None
    assert moved_disabled.disabled_by is None
    assert (
        "Detected code that sets disabled_by to DeviceEntryDisabler.CONFIG_ENTRY "
        f"when moving a device to the enabled config entry {enabled_entry.entry_id}. "
        "This will stop working in Home Assistant 2027.8, please report this issue"
    ) in caplog.text

    # The same validation applies when the move is performed by removing the
    # owning config entry after a pending move was recorded.
    pending_device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id, identifiers={("test", "3")}
    )
    device_registry.async_update_device(
        pending_device.id, add_config_entry_id=disabled_entry.entry_id
    )
    caplog.clear()
    moved_pending = device_registry.async_update_device(
        pending_device.id,
        disabled_by=None,
        remove_config_entry_id=enabled_entry.entry_id,
    )
    assert moved_pending is not None
    assert moved_pending.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert (
        "Detected code that sets disabled_by to None when moving a device to the "
        f"disabled config entry {disabled_entry.entry_id}. This will stop working "
        "in Home Assistant 2027.8, please report this issue"
    ) in caplog.text


async def test_update_conflicting_disabled_by_ignored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An explicit disabled_by contradicting the owning entry's disabled state.

    Without a move, the conflicting disabled_by is ignored and a deprecation
    warning is logged. This will raise in HA Core 2027.8.
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
    updated = device_registry.async_update_device(device.id, disabled_by=None)
    assert updated is not None
    assert updated.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert (
        "Detected code that sets disabled_by to None on a device belonging to the "
        f"disabled config entry {disabled_entry.entry_id}. This will stop working "
        "in Home Assistant 2027.8, please report this issue"
    ) in caplog.text

    enabled_device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id, identifiers={("test", "2")}
    )
    updated_enabled = device_registry.async_update_device(
        enabled_device.id, disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY
    )
    assert updated_enabled is not None
    assert updated_enabled.disabled_by is None
    assert (
        "Detected code that sets disabled_by to DeviceEntryDisabler.CONFIG_ENTRY on "
        f"a device belonging to the enabled config entry {enabled_entry.entry_id}. "
        "This will stop working in Home Assistant 2027.8, please report this issue"
    ) in caplog.text


async def test_create_with_conflicting_disabled_by_ignored(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An explicit disabled_by contradicting the owning entry's disabled state.

    When creating a device, the conflicting disabled_by is ignored, the disabled
    state is updated to reflect the owning config entry's disabled state, and a
    deprecation warning is logged. This will raise in HA Core 2027.8.
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
        disabled_by=None,
    )
    assert device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert (
        "Detected code that sets disabled_by to None when creating a device "
        f"attached to the disabled config entry {disabled_entry.entry_id}. This "
        "will stop working in Home Assistant 2027.8, please report this issue"
    ) in caplog.text

    enabled_device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id,
        identifiers={("test", "2")},
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )
    assert enabled_device.disabled_by is None
    assert (
        "Detected code that sets disabled_by to DeviceEntryDisabler.CONFIG_ENTRY "
        "when creating a device attached to the enabled config entry "
        f"{enabled_entry.entry_id}. This will stop working in Home Assistant "
        "2027.8, please report this issue"
    ) in caplog.text


async def test_create_reflects_config_entry_disabled_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A new device without an explicit disabled_by reflects the owning entry's state."""
    disabled_entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_hass(hass)
    enabled_entry = MockConfigEntry()
    enabled_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id, identifiers={("test", "1")}
    )
    assert device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    enabled_device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id, identifiers={("test", "2")}
    )
    assert enabled_device.disabled_by is None

    # Restoring a deleted device from a legacy store without a recorded
    # disabled_by is reconciled the same way
    device_registry.async_remove_device(device.id)
    deleted_entry = device_registry._deleted_devices[device.id]
    device_registry._deleted_devices[device.id] = attr.evolve(
        deleted_entry, disabled_by=UNDEFINED
    )
    restored = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id, identifiers={("test", "1")}
    )
    assert restored.id == device.id
    assert restored.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    assert "Detected code that" not in caplog.text


async def test_update_explicit_disabled_by(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An explicit disabled_by consistent with the owning entry's state is applied."""
    disabled_entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_hass(hass)
    enabled_entry = MockConfigEntry()
    enabled_entry.add_to_hass(hass)

    # A USER disable is accepted on a device of a disabled entry, and the device
    # can be flagged CONFIG_ENTRY again
    device = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id,
        identifiers={("test", "1")},
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )
    updated = device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    assert updated is not None
    assert updated.disabled_by is dr.DeviceEntryDisabler.USER
    updated = device_registry.async_update_device(
        device.id, disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY
    )
    assert updated is not None
    assert updated.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    # A USER disable and enabling are accepted on a device of an enabled entry
    enabled_device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id, identifiers={("test", "2")}
    )
    updated_enabled = device_registry.async_update_device(
        enabled_device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    assert updated_enabled is not None
    assert updated_enabled.disabled_by is dr.DeviceEntryDisabler.USER
    updated_enabled = device_registry.async_update_device(
        enabled_device.id, disabled_by=None
    )
    assert updated_enabled is not None
    assert updated_enabled.disabled_by is None

    assert "Detected code that" not in caplog.text


async def test_move_with_explicit_disabled_by(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An explicit disabled_by consistent with the target entry's state is applied."""
    disabled_entry = MockConfigEntry(
        disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_hass(hass)
    enabled_entry = MockConfigEntry()
    enabled_entry.add_to_hass(hass)

    # A USER disable is accepted on a move to a disabled entry
    device = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id, identifiers={("test", "1")}
    )
    moved = device_registry.async_update_device(
        device.id,
        disabled_by=dr.DeviceEntryDisabler.USER,
        new_config_entry_id=disabled_entry.entry_id,
    )
    assert moved is not None
    assert moved.disabled_by is dr.DeviceEntryDisabler.USER

    # A USER disable is accepted on a move to an enabled entry (the
    # CONFIG_ENTRY to USER rewrite used by migrations)
    device_2 = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id,
        identifiers={("test", "2")},
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )
    moved_2 = device_registry.async_update_device(
        device_2.id,
        disabled_by=dr.DeviceEntryDisabler.USER,
        new_config_entry_id=enabled_entry.entry_id,
    )
    assert moved_2 is not None
    assert moved_2.disabled_by is dr.DeviceEntryDisabler.USER

    # A CONFIG_ENTRY disable is accepted on a move to a disabled entry
    device_3 = device_registry.async_get_or_create(
        config_entry_id=enabled_entry.entry_id,
        identifiers={("test", "3")},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    moved_3 = device_registry.async_update_device(
        device_3.id,
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
        new_config_entry_id=disabled_entry.entry_id,
    )
    assert moved_3 is not None
    assert moved_3.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    # No disable is accepted on a move to an enabled entry
    device_4 = device_registry.async_get_or_create(
        config_entry_id=disabled_entry.entry_id,
        identifiers={("test", "4")},
        disabled_by=dr.DeviceEntryDisabler.USER,
    )
    moved_4 = device_registry.async_update_device(
        device_4.id,
        disabled_by=None,
        new_config_entry_id=enabled_entry.entry_id,
    )
    assert moved_4 is not None
    assert moved_4.disabled_by is None


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

    To the split in the child's own config entry when the parent spanned it, then to a
    split owned by the child's domain, otherwise to one of the parent's splits - never
    left dangling on the removed composite id.
    """
    entry_a = MockConfigEntry(domain="dom_a")
    entry_a.add_to_hass(hass)
    entry_a2 = MockConfigEntry(domain="dom_a")
    entry_a2.add_to_hass(hass)
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
                # child in another config entry of dom_a, which the parent does not span
                _device(
                    "childa200000000000000000000000",
                    [entry_a2.entry_id],
                    [["dom_a", "c2"]],
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

    # The child in entry_a2, which the parent did not span, points at the parent's
    # split owned by its domain
    child_a2 = registry.async_get_device(identifiers={("dom_a", "c2")})
    assert child_a2 is not None
    assert child_a2.via_device_id == parent_a.id

    # The child in entry_c, which the parent did not span, points at one of the parent's
    # splits rather than the removed composite id
    child_c = registry.async_get_device(identifiers={("dom_c", "c")})
    assert child_c is not None
    assert child_c.via_device_id in {parent_a.id, parent_b.id}


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_from_3_1_rewrites_stale_via_device_id(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Stale via_device_id links are remapped or detached when migrating from 3.1."""
    entry_a = MockConfigEntry(domain="dom_a")
    entry_a.add_to_hass(hass)
    entry_a2 = MockConfigEntry(domain="dom_a")
    entry_a2.add_to_hass(hass)
    entry_b = MockConfigEntry(domain="dom_b")
    entry_b.add_to_hass(hass)
    entry_c = MockConfigEntry(domain="dom_c")
    entry_c.add_to_hass(hass)
    composite_id = "composite000000000000000000000"

    def _device(
        id_: str,
        config_entry_id: str,
        identifiers: list[list[str]],
        via: str | None,
        composite: str | None = None,
    ) -> dict[str, Any]:
        return {
            "area_id": None,
            "config_entry_id": config_entry_id,
            "config_subentry_id": None,
            "configuration_url": None,
            "connections": [],
            "created_at": "1970-01-01T00:00:00+00:00",
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": id_,
            "identifiers": identifiers,
            "labels": [],
            "composite_device_id": composite,
            "composite_primary_config_entry": None,
            "split_at": None,
            "manufacturer": None,
            "model": None,
            "model_id": None,
            "modified_at": "1970-01-01T00:00:00+00:00",
            "name_by_user": None,
            "name": None,
            "has_composite_identifiers": composite is not None,
            "primary_config_entry": config_entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": via,
        }

    hass_storage[dr.STORAGE_KEY] = {
        "version": 3,
        "minor_version": 1,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                _device(
                    "splita000000000000000000000000",
                    entry_a.entry_id,
                    [["dom_a", "p"]],
                    None,
                    composite=composite_id,
                ),
                _device(
                    "splitb000000000000000000000000",
                    entry_b.entry_id,
                    [["dom_b", "p"]],
                    None,
                    composite=composite_id,
                ),
                # composite link from an entry the parent spans: its split
                _device(
                    "childa000000000000000000000000",
                    entry_a.entry_id,
                    [["dom_a", "c"]],
                    composite_id,
                ),
                # composite link from another entry of a split's domain: that split
                _device(
                    "childa200000000000000000000000",
                    entry_a2.entry_id,
                    [["dom_a", "c2"]],
                    composite_id,
                ),
                # composite link sharing neither entry nor domain: any split
                _device(
                    "childc000000000000000000000000",
                    entry_c.entry_id,
                    [["dom_c", "c"]],
                    composite_id,
                ),
                # link to an unknown device: detached
                _device(
                    "childx000000000000000000000000",
                    entry_a.entry_id,
                    [["dom_a", "cx"]],
                    "unknown0000000000000000000000",
                ),
                # link to a live device: kept
                _device(
                    "childl000000000000000000000000",
                    entry_a.entry_id,
                    [["dom_a", "cl"]],
                    "splitb000000000000000000000000",
                ),
            ],
            "deleted_devices": [],
        },
    }
    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    assert (
        registry._devices["childa000000000000000000000000"].via_device_id
        == "splita000000000000000000000000"
    )
    assert (
        registry._devices["childa200000000000000000000000"].via_device_id
        == "splita000000000000000000000000"
    )
    assert registry._devices["childc000000000000000000000000"].via_device_id in {
        "splita000000000000000000000000",
        "splitb000000000000000000000000",
    }
    assert registry._devices["childx000000000000000000000000"].via_device_id is None
    assert (
        registry._devices["childl000000000000000000000000"].via_device_id
        == "splitb000000000000000000000000"
    )


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
    assert len(device_registry._deleted_devices) == 3

    dr.async_cleanup(hass, device_registry, entity_registry)

    assert len(device_registry.devices) == 0
    assert len(device_registry._deleted_devices) == 3

    future_time = time.time() + dr.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        dr.async_cleanup(hass, device_registry, entity_registry)

    assert len(device_registry.devices) == 0
    assert len(device_registry._deleted_devices) == 0


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
    assert len(device_registry._deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry._deleted_devices) == 1

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
    assert len(device_registry._deleted_devices) == 0

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
    ("stored_connections", "stored_identifiers", "new_connections", "new_identifiers"),
    [
        pytest.param(
            {(dr.CONNECTION_NETWORK_MAC, "aa:aa:aa:aa:aa:aa")},
            {("bridgeid", "0123")},
            {
                (dr.CONNECTION_NETWORK_MAC, "aa:aa:aa:aa:aa:aa"),
                (dr.CONNECTION_NETWORK_MAC, "bb:bb:bb:bb:bb:bb"),
            },
            {("bridgeid", "0123"), ("bridgeid", "4567")},
            id="broader_reregistration",
        ),
        pytest.param(
            {(dr.CONNECTION_NETWORK_MAC, "aa:aa:aa:aa:aa:aa")},
            {("bridgeid", "0123")},
            {(dr.CONNECTION_NETWORK_MAC, "bb:bb:bb:bb:bb:bb")},
            {("bridgeid", "0123")},
            id="disjoint_connection_matched_on_identifier",
        ),
    ],
)
async def test_restore_device_reflects_reregistered_identity(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    stored_connections: set[tuple[str, str]],
    stored_identifiers: set[tuple[str, str]],
    new_connections: set[tuple[str, str]],
    new_identifiers: set[tuple[str, str]],
) -> None:
    """A restored device keeps the connections and identifiers it is re-registered with.

    The restored device must reflect the identity the integration reports on
    re-registration, not its intersection with the stored (deleted) identity, so a
    device that now reports a broader (or shifted) set is restored with all of it.
    """
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections=stored_connections,
        identifiers=stored_identifiers,
    )
    device_registry.async_remove_device(entry.id)
    assert len(device_registry._deleted_devices) == 1

    restored = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections=new_connections,
        identifiers=new_identifiers,
    )

    assert restored.id == entry.id
    assert restored.connections == new_connections
    assert restored.identifiers == new_identifiers


@pytest.mark.parametrize(
    ("new_connections", "new_identifiers"),
    [
        pytest.param(
            {
                (dr.CONNECTION_NETWORK_MAC, "aa:aa:aa:aa:aa:aa"),
                (dr.CONNECTION_NETWORK_MAC, "bb:bb:bb:bb:bb:bb"),
            },
            {("bridgeid", "0123"), ("bridgeid", "4567")},
            id="broader_reregistration",
        ),
        pytest.param(
            {(dr.CONNECTION_NETWORK_MAC, "cc:cc:cc:cc:cc:cc")},
            {("bridgeid", "9999")},
            id="disjoint_reregistration",
        ),
    ],
)
async def test_deleted_device_to_device_entry_uses_reregistered_identity(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    new_connections: set[tuple[str, str]],
    new_identifiers: set[tuple[str, str]],
) -> None:
    """DeletedDeviceEntry.to_device_entry keeps the passed connections and identifiers.

    Regression guard: it must not intersect them with the stored ones, which would drop
    (or, for a disjoint re-registration, entirely empty) the device's identity.
    """
    entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "aa:aa:aa:aa:aa:aa")},
        identifiers={("bridgeid", "0123")},
    )
    device_registry.async_remove_device(entry.id)
    deleted_device = device_registry._deleted_devices[entry.id]

    restored = deleted_device.to_device_entry(
        mock_config_entry,
        None,
        new_connections,
        new_identifiers,
        None,
    )

    assert restored.connections == new_connections
    assert restored.identifiers == new_identifiers


@pytest.mark.parametrize(
    ("device_disabled_by", "expected_disabled_by"),
    [
        (None, None),
        # A CONFIG_ENTRY disable contradicts the enabled config entry and is
        # cleared when the device is restored
        (dr.DeviceEntryDisabler.CONFIG_ENTRY, None),
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
    assert len(device_registry._deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry._deleted_devices) == 1

    deleted_entry = device_registry._deleted_devices[entry.id]
    device_registry._deleted_devices[entry.id] = attr.evolve(
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
    assert len(device_registry._deleted_devices) == 0

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
        "device_disabled_by_deleted",
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
    device_disabled_by_deleted: dr.DeviceEntryDisabler | None,
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
    assert len(device_registry._deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry._deleted_devices) == 1

    # Simulate the disabled_by flag the device had when it was deleted. The
    # device may have been deleted before the config entry's disabled state
    # last changed - deleted devices are not updated when a config entry is
    # enabled or disabled, so the stored flag can contradict the entry's
    # current disabled state.
    deleted_entry = device_registry._deleted_devices[entry.id]
    device_registry._deleted_devices[entry.id] = attr.evolve(
        deleted_entry, disabled_by=device_disabled_by_deleted
    )

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
    assert len(device_registry._deleted_devices) == 0

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


@pytest.mark.parametrize(
    ("field", "default_field"),
    [
        ("name", "default_name"),
        ("manufacturer", "default_manufacturer"),
        ("model", "default_model"),
    ],
)
async def test_get_or_create_rejects_field_and_its_default(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    field: str,
    default_field: str,
) -> None:
    """Test passing both an explicit field and its default_ counterpart is rejected."""
    with pytest.raises(
        dr.DeviceInfoError,
        match=f"passing both `{field}` and `{default_field}` is not allowed",
    ):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
            **{field: "explicit value", default_field: "default value"},
        )


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
            "child_devices": [],
            "devices": [
                {
                    "area_id": None,
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

    # Implicitly merging a connection registered to another device of the same
    # config entry raises
    with pytest.raises(dr.DeviceInfoError, match="already registered"):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("bridgeid", "0123")},
            connections={
                (dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE"),
                (dr.CONNECTION_NETWORK_MAC, "none"),
            },
        )
    assert len(device_registry.devices) == 2

    device3_refetched = device_registry.async_get(device3.id)
    assert device3_refetched.connections == set()
    device1_refetched = device_registry.async_get(device1.id)
    assert device1_refetched.connections == {(dr.CONNECTION_NETWORK_MAC, "none")}


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

    # Implicitly merging an identifier registered to another device of the same
    # config entry raises
    with pytest.raises(dr.DeviceInfoError, match="already registered"):
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("bridgeid", "4567"), ("bridgeid", "0123")},
        )
    assert len(device_registry.devices) == 2

    device3_refetched = device_registry.async_get(device3.id)
    assert device3_refetched.identifiers == {("bridgeid", "4567")}
    device1_refetched = device_registry.async_get(device1.id)
    assert device1_refetched.identifiers == {("bridgeid", "0123")}


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
    assert len(device_registry._deleted_devices) == 0

    device_registry.async_remove_device(device1.id)
    assert len(device_registry._deleted_devices) == 1

    device2 = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert len(device_registry._deleted_devices) == 1

    device_registry.async_update_device(
        device2.id,
        merge_connections={(dr.CONNECTION_NETWORK_MAC, "EE:EE:EE:EE:EE:EE")},
    )
    assert len(device_registry._deleted_devices) == 0


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
    assert shadowed.id in device_registry._devices

    # Remove the shadowed device, then the indexed one - neither must raise
    device_registry.async_remove_device(shadowed.id)
    device_registry.async_remove_device(device.id)

    # The second config entry's device is still reachable by the shared identifier
    assert (
        device_registry.async_get_device(identifiers={("test", "2")})
        is other_entry_device
    )


async def test_remove_device_promotes_shadowed_duplicate(
    hass: HomeAssistant,
) -> None:
    """Removing the indexed holder of a duplicate key promotes the shadowed one."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_registry = mock_device_registry(
        hass,
        {
            "shadowed": dr.DeviceEntry(
                id="shadowed",
                config_entry_id=entry.entry_id,
                identifiers={("test", "shared")},
            ),
            "winner": dr.DeviceEntry(
                id="winner",
                config_entry_id=entry.entry_id,
                identifiers={("test", "shared")},
            ),
        },
    )
    assert (
        device_registry.async_get_device(identifiers={("test", "shared")}).id
        == "winner"
    )

    device_registry.async_remove_device("winner")

    assert (
        device_registry.async_get_device(identifiers={("test", "shared")}).id
        == "shadowed"
    )


async def test_update_device_reindexes_shadowed_duplicate(
    hass: HomeAssistant,
) -> None:
    """Updating a shadowed duplicate re-indexes it, so it wins the lookups."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_registry = mock_device_registry(
        hass,
        {
            "shadowed": dr.DeviceEntry(
                id="shadowed",
                config_entry_id=entry.entry_id,
                identifiers={("test", "shared")},
            ),
            "winner": dr.DeviceEntry(
                id="winner",
                config_entry_id=entry.entry_id,
                identifiers={("test", "shared")},
            ),
        },
    )
    assert (
        device_registry.async_get_device(identifiers={("test", "shared")}).id
        == "winner"
    )

    # The updated shadowed duplicate takes over the lookup slot (last indexed wins)
    device_registry.async_update_device("shadowed", name_by_user="renamed")
    assert (
        device_registry.async_get_device(identifiers={("test", "shared")}).id
        == "shadowed"
    )

    # An updated slot holder stays in the slot
    device_registry.async_update_device("shadowed", name_by_user="renamed again")
    assert (
        device_registry.async_get_device(identifiers={("test", "shared")}).id
        == "shadowed"
    )
    assert len(device_registry.devices) == 2


@pytest.mark.parametrize(
    ("device_extra", "stale_extra", "register_extra"),
    [
        pytest.param(
            {"identifiers": {("test", "device"), ("test", "shared")}},
            {"identifiers": {("test", "stale"), ("test", "shared")}},
            {"identifiers": {("test", "device")}},
            id="identifiers",
        ),
        pytest.param(
            {
                "identifiers": {("test", "device")},
                "connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
            },
            {
                "identifiers": {("test", "stale")},
                "connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
            },
            {
                "identifiers": {("test", "device")},
                "connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
            },
            id="connections",
        ),
    ],
)
async def test_legacy_duplicate_keys_stripped_on_registration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    device_extra: dict[str, set[tuple[str, str]]],
    stale_extra: dict[str, set[tuple[str, str]]],
    register_extra: dict[str, set[tuple[str, str]]],
) -> None:
    """Registering a device strips its keys from stale same-entry duplicates.

    The stale duplicate keeps its other keys; another config entry is not affected.
    """
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="test")
    other_entry.add_to_hass(hass)
    shared_keys = device_extra.keys() & stale_extra.keys()
    device_registry = mock_device_registry(
        hass,
        {
            "device": dr.DeviceEntry(
                id="device", config_entry_id=entry.entry_id, **device_extra
            ),
            "stale": dr.DeviceEntry(
                id="stale", config_entry_id=entry.entry_id, **stale_extra
            ),
            "other": dr.DeviceEntry(
                id="other",
                config_entry_id=other_entry.entry_id,
                **{key: device_extra[key] & stale_extra[key] for key in shared_keys},
            ),
        },
    )

    registered = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, **register_extra
    )

    assert registered.id == "device"
    assert registered.identifiers == device_extra["identifiers"]
    assert registered.connections == device_extra.get("connections", set())
    # The stale duplicate lost the shared keys but keeps its own
    stale = device_registry.async_get("stale")
    assert stale.identifiers == {("test", "stale")}
    assert stale.connections == set()
    # The registered device is reachable by the previously shared keys
    assert (
        _get_device_for_config_entry(
            device_registry,
            entry.entry_id,
            identifiers=device_extra["identifiers"],
            connections=device_extra.get("connections"),
        ).id
        == "device"
    )
    # A device of another config entry sharing a key is not affected
    other = device_registry.async_get("other")
    assert other.identifiers == device_extra["identifiers"] & stale_extra["identifiers"]
    assert other.connections == device_extra.get(
        "connections", set()
    ) & stale_extra.get("connections", set())
    # Registering again is a no-op
    registered = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, **register_extra
    )
    assert registered.id == "device"
    assert len(device_registry.devices) == 3
    # The stripped keys are persisted
    await flush_store(device_registry._store)
    stored_stale = next(
        device
        for device in hass_storage[dr.STORAGE_KEY]["data"]["devices"]
        if device["id"] == "stale"
    )
    assert {tuple(identifier) for identifier in stored_stale["identifiers"]} == {
        ("test", "stale")
    }
    assert stored_stale["connections"] == []


async def test_legacy_duplicate_fully_stripped_device_removed(
    hass: HomeAssistant,
) -> None:
    """A stale duplicate left without any keys is removed, also from deleted devices."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_registry = mock_device_registry(
        hass,
        {
            "device": dr.DeviceEntry(
                id="device",
                config_entry_id=entry.entry_id,
                identifiers={("test", "device"), ("test", "shared")},
            ),
            "stale": dr.DeviceEntry(
                id="stale",
                config_entry_id=entry.entry_id,
                identifiers={("test", "shared")},
            ),
        },
    )

    registered = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "device")}
    )

    assert registered.id == "device"
    assert registered.identifiers == {("test", "device"), ("test", "shared")}
    assert device_registry.async_get("stale") is None
    assert "stale" not in device_registry._deleted_devices
    assert (
        device_registry.async_get_device(identifiers={("test", "shared")}).id
        == "device"
    )


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_from_storage_with_legacy_duplicates(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Duplicates from an old store are tracked on load and reconciled on registration."""
    entry_id = mock_config_entry.entry_id
    created_at = "2024-01-01T00:00:00+00:00"

    def _stored_device(
        device_id: str, identifiers: list[list[str]], connections: list[list[str]]
    ) -> dict[str, Any]:
        return {
            "area_id": None,
            "config_entries": [entry_id],
            "config_entries_subentries": {entry_id: [None]},
            "config_entry_id": entry_id,
            "config_subentry_id": None,
            "composite_device_id": None,
            "composite_primary_config_entry": None,
            "split_at": None,
            "has_composite_identifiers": False,
            "configuration_url": None,
            "connections": connections,
            "created_at": created_at,
            "disabled_by": None,
            "entry_type": None,
            "hw_version": None,
            "id": device_id,
            "identifiers": identifiers,
            "labels": [],
            "manufacturer": None,
            "model": None,
            "model_id": None,
            "modified_at": created_at,
            "name_by_user": None,
            "name": None,
            "primary_config_entry": entry_id,
            "serial_number": None,
            "sw_version": None,
            "via_device_id": None,
        }

    hass_storage[dr.STORAGE_KEY] = {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "data": {
            "child_devices": [],
            "devices": [
                _stored_device(
                    "old",
                    [["test", "shared"]],
                    [[dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef"]],
                ),
                _stored_device(
                    "new",
                    [["test", "shared"], ["test", "own"]],
                    [[dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef"]],
                ),
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    assert (
        "Loaded 2 identifiers/connections registered to multiple devices of one "
        "config entry" in caplog.text
    )
    # The last stored duplicate wins the lookups
    assert registry.async_get_device(identifiers={("test", "shared")}).id == "new"
    assert (
        registry.async_get_device(
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")}
        ).id
        == "new"
    )
    assert len(registry.devices) == 2

    # Registration reconciles: the fully shadowed duplicate is removed
    registered = registry.async_get_or_create(
        config_entry_id=entry_id,
        identifiers={("test", "shared")},
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
    )
    assert registered.id == "new"
    assert registry.async_get("old") is None
    assert "old" not in registry._deleted_devices

    # The reconciled state is persisted
    await flush_store(registry._store)
    stored_devices = hass_storage[dr.STORAGE_KEY]["data"]["devices"]
    assert [device["id"] for device in stored_devices] == ["new"]
    assert hass_storage[dr.STORAGE_KEY]["data"]["deleted_devices"] == []


async def test_registration_purges_same_entry_deleted_duplicates(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Registering a device purges same-entry deleted devices holding its keys.

    Whole records are purged, shadowed included; another config entry is not affected.
    """
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(domain="test")
    other_entry.add_to_hass(hass)
    device_registry = mock_device_registry(
        hass,
        {
            "device": dr.DeviceEntry(
                id="device",
                config_entry_id=entry.entry_id,
                identifiers={("test", "device"), ("test", "shared")},
            ),
        },
    )
    device_registry._deleted_devices["deleted_shadowed"] = _mock_deleted_device(
        "deleted_shadowed", entry.entry_id, {("test", "shared"), ("test", "other")}
    )
    device_registry._deleted_devices["deleted_winner"] = _mock_deleted_device(
        "deleted_winner", entry.entry_id, {("test", "shared")}
    )
    device_registry._deleted_devices["deleted_other_entry"] = _mock_deleted_device(
        "deleted_other_entry", other_entry.entry_id, {("test", "shared")}
    )

    registered = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "device")}
    )

    assert registered.id == "device"
    assert "deleted_winner" not in device_registry._deleted_devices
    assert "deleted_shadowed" not in device_registry._deleted_devices
    assert "deleted_other_entry" in device_registry._deleted_devices
    # The purge is persisted
    await flush_store(device_registry._store)
    assert [
        device["id"]
        for device in hass_storage[dr.STORAGE_KEY]["data"]["deleted_devices"]
    ] == ["deleted_other_entry"]


async def test_restore_purges_same_entry_deleted_duplicate(
    hass: HomeAssistant,
) -> None:
    """Restoring a deleted device purges its same-entry deleted duplicates."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_registry = mock_device_registry(hass)
    device_registry._deleted_devices["deleted_shadowed"] = _mock_deleted_device(
        "deleted_shadowed", entry.entry_id, {("test", "shared")}
    )
    device_registry._deleted_devices["deleted_winner"] = _mock_deleted_device(
        "deleted_winner", entry.entry_id, {("test", "shared")}
    )

    restored = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "shared")}
    )

    assert restored.id == "deleted_winner"
    assert "deleted_winner" not in device_registry._deleted_devices
    assert "deleted_shadowed" not in device_registry._deleted_devices
    assert len(device_registry.devices) == 1


async def test_add_identifier_prunes_shadowed_deleted_duplicates(
    hass: HomeAssistant,
) -> None:
    """Gaining an identifier removes all matching same-entry deleted devices.

    Whole records are removed, shadowed duplicates included.
    """
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_registry = mock_device_registry(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("test", "device")}
    )
    device_registry._deleted_devices["deleted_shadowed"] = _mock_deleted_device(
        "deleted_shadowed", entry.entry_id, {("test", "shared")}
    )
    device_registry._deleted_devices["deleted_winner"] = _mock_deleted_device(
        "deleted_winner", entry.entry_id, {("test", "shared"), ("test", "other")}
    )

    device_registry.async_update_device(
        device.id, merge_identifiers={("test", "shared")}
    )

    assert "deleted_winner" not in device_registry._deleted_devices
    assert "deleted_shadowed" not in device_registry._deleted_devices


async def test_via_device_id_to_removed_stale_duplicate_raises(
    hass: HomeAssistant,
) -> None:
    """A via_device_id to a stale duplicate removed by reconciliation raises."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    device_registry = mock_device_registry(
        hass,
        {
            "device": dr.DeviceEntry(
                id="device",
                config_entry_id=entry.entry_id,
                identifiers={("test", "device"), ("test", "shared")},
            ),
            "stale": dr.DeviceEntry(
                id="stale",
                config_entry_id=entry.entry_id,
                identifiers={("test", "shared")},
            ),
        },
    )

    with pytest.raises(dr.DeviceInfoError, match="not a registered device id"):
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("test", "device")},
            via_device_id="stale",
        )
    assert device_registry.async_get("stale") is None


async def test_key_collision_reconciled_after_config_entry_reload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A key moved between devices raises while loaded and reconciles after reload."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "test.config_flow", None)

    class MockFlow(config_entries.ConfigFlow):
        """Test flow."""

    with mock_config_flow("test", MockFlow):
        assert await hass.config_entries.async_setup(entry.entry_id)

        connection = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
        device_a = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("test", "device_a")},
            connections={connection},
        )
        device_b = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("test", "device_b")},
        )

        # Both devices are registered this setup session, so moving the key raises
        with pytest.raises(dr.DeviceInfoError, match="already registered"):
            device_registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={("test", "device_b")},
                connections={connection},
            )
        device_a_refetched = device_registry.async_get(device_a.id)
        assert device_a_refetched is not None
        assert device_a_refetched.connections == {connection}

        assert await hass.config_entries.async_unload(entry.entry_id)
        assert await hass.config_entries.async_setup(entry.entry_id)

        # In the new setup session the registering device is authoritative
        device_b_refetched = device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={("test", "device_b")},
            connections={connection},
        )
        assert device_b_refetched.id == device_b.id
        assert device_b_refetched.connections == {connection}
        device_a_refetched = device_registry.async_get(device_a.id)
        assert device_a_refetched is not None
        assert device_a_refetched.connections == set()


async def test_key_collision_reconciled_after_setup_retry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A key moved between devices reconciles on the retry after a failed setup."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    connection = (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")

    async def first_attempt(
        hass: HomeAssistant, config_entry: config_entries.ConfigEntry
    ) -> bool:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", "device_a")},
            connections={connection},
        )
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", "device_b")},
        )
        raise ConfigEntryNotReady

    async def second_attempt(
        hass: HomeAssistant, config_entry: config_entries.ConfigEntry
    ) -> bool:
        device_registry.async_get_or_create(
            config_entry_id=config_entry.entry_id,
            identifiers={("test", "device_b")},
            connections={connection},
        )
        return True

    attempts = [first_attempt, second_attempt]

    async def async_setup_entry(
        hass: HomeAssistant, config_entry: config_entries.ConfigEntry
    ) -> bool:
        return await attempts.pop(0)(hass, config_entry)

    mock_integration(hass, MockModule("test", async_setup_entry=async_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    class MockFlow(config_entries.ConfigFlow):
        """Test flow."""

    with mock_config_flow("test", MockFlow):
        await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY

        async_fire_time_changed(hass, utcnow() + timedelta(seconds=30))
        await hass.async_block_till_done()

    # The retry reconciled the key away from the failed attempt's device
    assert entry.state is config_entries.ConfigEntryState.LOADED
    device_b = device_registry.async_get_device(identifiers={("test", "device_b")})
    assert device_b is not None
    assert device_b.connections == {connection}
    device_a = device_registry.async_get_device(identifiers={("test", "device_a")})
    assert device_a is not None
    assert device_a.connections == set()


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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
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


async def test_composite_move_unknown_via_device_id_keeps_sibling_moves(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """An unknown via_device_id raises before a move clears sibling pending moves."""
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
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=old_id
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=old_id
    )

    # Arm a deferred move on the composite id: fans out to both splits
    with patch.object(dr, "_current_integration_domain", return_value="test"):
        device_registry.async_update_device(
            old_id, add_config_entry_id=entry_target.entry_id
        )

    # The failed call must not move the device or clear the sibling's pending move
    with (
        patch.object(dr, "_current_integration_domain", return_value="test"),
        pytest.raises(HomeAssistantError, match="unknown via device unknown-device-id"),
    ):
        device_registry.async_update_device(
            device_1.id,
            remove_config_entry_id=entry_1.entry_id,
            via_device_id="unknown-device-id",
        )
    assert device_registry.async_get(device_1.id).config_entry_id == entry_1.entry_id
    assert device_registry.async_get(device_1.id)._pending_move is not None
    assert device_registry.async_get(device_2.id)._pending_move is not None

    # The armed moves are intact and can still complete
    with patch.object(dr, "_current_integration_domain", return_value="test"):
        device_registry.async_update_device(
            device_1.id, remove_config_entry_id=entry_1.entry_id
        )
    assert (
        device_registry.async_get(device_1.id).config_entry_id == entry_target.entry_id
    )
    assert device_registry.async_get(device_2.id)._pending_move is None


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
    assert COMPOSITE_ID not in device_registry._devices
    assert COMPOSITE_ID not in {d.id for d in device_registry.devices}
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
async def test_get_composite_splits(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test getting the mapping of composite device ids to their split devices."""
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
    split_b = _get_device_for_config_entry(
        device_registry, entry_b.entry_id, identifiers={("domain_b", "1")}
    )

    splits = device_registry._devices.get_composite_splits()
    assert set(splits) == {COMPOSITE_ID}
    assert {device.id for device in splits[COMPOSITE_ID]} == {split_a.id, split_b.id}

    # A device which is not split from a composite is not included
    device_registry.async_get_or_create(
        config_entry_id=entry_a.entry_id, identifiers={("domain_a", "2")}
    )
    splits = device_registry._devices.get_composite_splits()
    assert set(splits) == {COMPOSITE_ID}
    assert {device.id for device in splits[COMPOSITE_ID]} == {split_a.id, split_b.id}

    # A removed split is dropped from the mapping
    device_registry.async_remove_device(split_a.id)
    splits = device_registry._devices.get_composite_splits()
    assert {device.id for device in splits[COMPOSITE_ID]} == {split_b.id}

    # Removing the last split drops the composite id from the mapping
    device_registry.async_remove_device(split_b.id)
    assert device_registry._devices.get_composite_splits() == {}


async def test_async_get_device_and_config_entry_for_domain(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test getting the device and config entry of a domain owning a device."""
    entry = MockConfigEntry(domain="domain_a")
    entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={("domain_a", "1")}
    )

    assert dr.async_get_device_and_config_entry_for_domain(
        hass, device.id, domain="domain_a"
    ) == (device, entry)
    # A domain not owning the device still gets the device
    assert dr.async_get_device_and_config_entry_for_domain(
        hass, device.id, domain="domain_b"
    ) == (device, None)
    # An unknown device id
    assert dr.async_get_device_and_config_entry_for_domain(
        hass, "unknown_id", domain="domain_a"
    ) == (None, None)


@pytest.mark.parametrize("load_registries", [False])
async def test_async_get_device_and_config_entry_for_domain_composite(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test getting the device and config entry via a composite device id."""
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
    split_b = _get_device_for_config_entry(
        device_registry, entry_b.entry_id, identifiers={("domain_b", "1")}
    )

    # The returned pair is consistent: the domain's split device, not the composite
    assert dr.async_get_device_and_config_entry_for_domain(
        hass, COMPOSITE_ID, domain="domain_a"
    ) == (split_a, entry_a)
    assert dr.async_get_device_and_config_entry_for_domain(
        hass, COMPOSITE_ID, domain="domain_b"
    ) == (split_b, entry_b)
    # A domain owning none of the splits gets the restored composite and no entry
    device, config_entry = dr.async_get_device_and_config_entry_for_domain(
        hass, COMPOSITE_ID, domain="domain_c"
    )
    assert config_entry is None
    assert device is not None
    assert device.id == COMPOSITE_ID
    assert device.config_entries == {entry_a.entry_id, entry_b.entry_id}


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


def _create_parent_and_child(
    device_registry: dr.DeviceRegistry,
    config_entry_id: str,
    *,
    config_subentry_id: str | UndefinedType = UNDEFINED,
) -> tuple[dr.DeviceEntry, dr.ChildDeviceEntry]:
    """Create a parent device with one child device."""
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry_id,
        config_subentry_id=config_subentry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=config_entry_id,
        config_subentry_id=config_subentry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    return parent, child_device


async def test_child_device_create(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a child device."""
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert isinstance(child_device, dr.ChildDeviceEntry)
    assert child_device.parent_device_id == parent.id
    assert child_device.config_entry_id == mock_config_entry.entry_id
    assert child_device.config_subentry_id is None
    assert child_device.identifiers == {("test", "strip_outlet_1")}
    assert child_device.name == "Outlet 1"
    assert child_device.area_id is None
    assert child_device.disabled_by is None

    assert device_registry.async_get(child_device.id) is child_device
    assert (
        device_registry.async_get(child_device.id, include_main_devices=False)
        is child_device
    )
    assert len(device_registry.devices) == 1
    assert len(device_registry.child_devices) == 1
    assert dr.async_entries_for_parent_device(device_registry, parent.id) == [
        child_device
    ]
    assert dr.async_child_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ) == [child_device]
    assert dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    ) == [parent]

    await hass.async_block_till_done()
    assert [event.data for event in update_events] == [
        {"action": "create", "device_id": parent.id},
        {"action": "create", "device_id": child_device.id},
    ]

    assert child_device.dict_repr == {
        "area_id": None,
        "config_entry_id": mock_config_entry.entry_id,
        "config_subentry_id": None,
        "created_at": child_device.created_at.timestamp(),
        "disabled_by": None,
        "id": child_device.id,
        "identifiers": [("test", "strip_outlet_1")],
        "labels": [],
        "modified_at": child_device.modified_at.timestamp(),
        "name_by_user": None,
        "name": "Outlet 1",
        "parent_device_id": parent.id,
    }


@pytest.mark.parametrize(
    ("attr_name", "expected_default"),
    [
        ("configuration_url", None),
        ("connections", set()),
        ("entry_type", None),
        ("hw_version", None),
        ("manufacturer", None),
        ("model", None),
        ("model_id", None),
        ("serial_number", None),
        ("sw_version", None),
        ("via_device_id", None),
    ],
)
@pytest.mark.parametrize(
    ("integration_frame_path", "expectation", "expected_log"),
    [
        pytest.param(
            "homeassistant/test_core", pytest.raises(AttributeError), 0, id="core"
        ),
        pytest.param(
            "homeassistant/components/test_integration",
            pytest.raises(AttributeError),
            0,
            id="core integration",
        ),
        pytest.param(
            "custom_components/test_integration",
            nullcontext(),
            1,
            id="custom integration",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_child_device_deprecated_device_entry_attrs(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    attr_name: str,
    expected_default: Any,
    expectation: AbstractContextManager,
    expected_log: int,
) -> None:
    """Test accessing a DeviceEntry-only attribute on a child device.

    Custom integrations get the DeviceEntry default value and a deprecation warning;
    core and core integrations raise AttributeError so the attribute reads as missing.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    what = (
        f"accesses ChildDeviceEntry.{attr_name}, which does not exist on child devices"
    )
    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()), expectation:
        assert getattr(child_device, attr_name) == expected_default
    assert caplog.text.count(what) == expected_log


@pytest.mark.parametrize("attr_name", sorted(dr._CHILD_DEVICE_COMPAT_ATTRS))
@pytest.mark.usefixtures("hass")
async def test_child_device_deprecated_attrs_missing_for_core(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    attr_name: str,
) -> None:
    """Test DeviceEntry-only attributes read as missing without an integration frame.

    This is the template/pure-core path: hasattr must be False so device_attr and
    is_device_attr fall back to None instead of raising.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert hasattr(child_device, attr_name) is False
    with pytest.raises(AttributeError, match=f"has no attribute '{attr_name}'"):
        getattr(child_device, attr_name)


@pytest.mark.usefixtures("hass")
async def test_child_device_unknown_attribute_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test accessing a genuinely unknown attribute on a child device raises."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(AttributeError, match="has no attribute 'does_not_exist'"):
        getattr(child_device, "does_not_exist")  # noqa: B009


@pytest.mark.usefixtures("hass")
async def test_async_get_exclude_child_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_get with include_child_devices=False treats children as absent."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert device_registry.async_get(child_device.id) is child_device
    assert device_registry.async_get(parent.id, include_child_devices=False) is parent
    assert (
        device_registry.async_get(child_device.id, include_child_devices=False) is None
    )


@pytest.mark.usefixtures("hass")
async def test_async_get_child_device_by_identifier(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test looking up a child device by identifier."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert (
        device_registry.async_get_child_device_by_identifier(
            ("test", "strip_outlet_1"), mock_config_entry.entry_id
        )
        is child_device
    )
    assert (
        device_registry.async_get_child_device_by_identifier(
            ("test", "unknown"), mock_config_entry.entry_id
        )
        is None
    )
    # Only child devices are searched, so a main device's identifier is not found
    assert (
        device_registry.async_get_child_device_by_identifier(
            ("test", "strip"), mock_config_entry.entry_id
        )
        is None
    )


@pytest.mark.usefixtures("hass")
async def test_child_device_create_idempotent(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-registering a child device is idempotent and applies updates."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    child_device_2 = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet one",
    )
    assert child_device_2.id == child_device.id
    assert child_device_2.name == "Outlet one"
    assert len(device_registry.child_devices) == 1


@pytest.mark.usefixtures("hass")
async def test_child_device_create_with_suggested_area(
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test suggested_area sets the initial area of a new child device only."""
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
        suggested_area="Garden",
    )
    garden = area_registry.async_get_area_by_name("Garden")
    assert garden is not None
    assert child_device.area_id == garden.id

    # suggested_area is a one-shot hint for a new child device
    child_device_2 = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
        suggested_area="Garage",
    )
    assert child_device_2.area_id == garden.id


@pytest.mark.parametrize(
    ("identifiers", "parent_key", "error"),
    [
        pytest.param(
            {("test", "strip_outlet_1")},
            "unknown",
            "must be created before its child devices",
            id="unknown_parent",
        ),
        pytest.param(
            {("test", "grandchild")},
            "child",
            "can't be the parent of another child device",
            id="parent_is_child",
        ),
        pytest.param(
            {("test", "strip_outlet_1")},
            "other_strip",
            "reparenting is not supported",
            id="reparent",
        ),
    ],
)
@pytest.mark.usefixtures("hass")
async def test_child_device_create_errors(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    identifiers: set[tuple[str, str]],
    parent_key: str,
    error: str,
) -> None:
    """Test invalid child device registrations raise DeviceInfoError."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    other_strip = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "other_strip")},
        name="Other strip",
    )
    parent_device_ids = {
        "unknown": "nonexistent-device-id",
        "child": child_device.id,
        "other_strip": other_strip.id,
    }

    with pytest.raises(dr.DeviceInfoError, match=error):
        device_registry.async_get_or_create_child(
            config_entry_id=mock_config_entry.entry_id,
            identifiers=identifiers,
            parent_device_id=parent_device_ids[parent_key],
            name="Nope",
        )

    # Validation precedes mutation, so the registry is unchanged by the rejection
    assert len(device_registry.devices) == 2
    assert len(device_registry.child_devices) == 1
    unchanged_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert unchanged_child is not None
    assert unchanged_child.parent_device_id == parent.id


async def test_child_device_parent_in_other_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a child device must share its parent's config entry."""
    other_entry = MockConfigEntry(title=None)
    other_entry.add_to_hass(hass)
    parent = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )

    with pytest.raises(dr.DeviceInfoError, match="same config entry"):
        device_registry.async_get_or_create_child(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "strip_outlet_1")},
            parent_device_id=parent.id,
            name="Outlet 1",
        )

    # Validation precedes mutation, so no child device is created
    assert not device_registry.child_devices
    assert len(device_registry.devices) == 1


@pytest.mark.usefixtures("hass")
async def test_child_device_subentry(
    device_registry: dr.DeviceRegistry,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test a child device lives in the same config subentry as its parent."""
    entry_id = mock_config_entry_with_subentries.entry_id
    parent, child_device = _create_parent_and_child(
        device_registry, entry_id, config_subentry_id="mock-subentry-id-1-1"
    )
    assert child_device.config_subentry_id == "mock-subentry-id-1-1"
    assert child_device.parent_device_id == parent.id

    # A child device in a different subentry than its parent is rejected
    with pytest.raises(dr.DeviceInfoError, match="same config subentry"):
        device_registry.async_get_or_create_child(
            config_entry_id=entry_id,
            config_subentry_id="mock-subentry-id-1-2",
            identifiers={("test", "strip_outlet_2")},
            parent_device_id=parent.id,
            name="Outlet 2",
        )
    with pytest.raises(dr.DeviceInfoError, match="same config subentry"):
        device_registry.async_get_or_create_child(
            config_entry_id=entry_id,
            identifiers={("test", "strip_outlet_2")},
            parent_device_id=parent.id,
            name="Outlet 2",
        )

    # Neither rejected registration created a child device
    assert len(device_registry.child_devices) == 1
    assert (
        device_registry.async_get_child_device_by_identifier(
            ("test", "strip_outlet_2"), entry_id
        )
        is None
    )


async def test_child_device_update(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating a child device."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    updated = device_registry.async_update_child_device(
        child_device.id,
        area_id="garden",
        labels={"outdoor"},
        name_by_user="Garden lamp plug",
    )
    assert isinstance(updated, dr.ChildDeviceEntry)
    assert updated.area_id == "garden"
    assert updated.labels == {"outdoor"}
    assert updated.name_by_user == "Garden lamp plug"

    # Clearing the area restores inheriting the parent's area
    updated = device_registry.async_update_child_device(child_device.id, area_id=None)
    assert updated.area_id is None

    await hass.async_block_till_done()
    assert [event.data for event in update_events] == [
        {
            "action": "update",
            "device_id": child_device.id,
            "changes": {"area_id": None, "labels": set(), "name_by_user": None},
        },
        {
            "action": "update",
            "device_id": child_device.id,
            "changes": {"area_id": "garden"},
        },
    ]


@pytest.mark.usefixtures("hass")
async def test_update_device_wrong_kind_of_device_id_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the split update API points at the correct method for the other kind."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(
        HomeAssistantError,
        match=f"Device {child_device.id} is a child device; "
        "use async_update_child_device",
    ):
        device_registry.async_update_device(child_device.id, name_by_user="Nope")

    with pytest.raises(
        HomeAssistantError,
        match=f"Device {parent.id} is a main device; use async_update_device",
    ):
        device_registry.async_update_child_device(parent.id, name_by_user="Nope")

    with pytest.raises(KeyError):
        device_registry.async_update_device("unknown-device-id")
    with pytest.raises(KeyError):
        device_registry.async_update_child_device("unknown-child-id")


@pytest.mark.usefixtures("hass")
async def test_update_main_device_rejects_disabled_by_device(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabled_by=DEVICE is rejected on a main device, on create and update.

    DeviceEntryDisabler.DEVICE means "disabled because the parent is disabled" and is
    only valid for a child device. The rejection runs before any registry mutation, so
    a rejected create leaves no phantom device behind and a rejected update leaves the
    device unchanged.
    """
    match = "disabled_by=DeviceEntryDisabler.DEVICE is only valid for a child device"

    # The create path rejects it, before a (phantom) device is created
    with pytest.raises(HomeAssistantError, match=match):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "main")},
            disabled_by=dr.DeviceEntryDisabler.DEVICE,
        )
    assert len(device_registry.devices) == 0

    # The update path rejects it, leaving the device unchanged
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "main")},
    )
    assert device.disabled_by is None
    with pytest.raises(HomeAssistantError, match=match):
        device_registry.async_update_device(
            device.id, disabled_by=dr.DeviceEntryDisabler.DEVICE
        )
    assert device_registry.async_get(device.id).disabled_by is None


@pytest.mark.usefixtures("hass")
async def test_get_or_create_disabled_by_device_does_not_restore_deleted_device(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabled_by=DEVICE matching a deleted device restores nothing.

    A legacy deleted device (its stored disabled_by is UNDEFINED) restores with the
    caller's disabled_by verbatim, so without an early guard a caller-passed DEVICE
    would restore a main device disabled by DEVICE. The rejection must run before the
    restore.
    """
    match = "disabled_by=DeviceEntryDisabler.DEVICE is only valid for a child device"
    identifiers = {("test", "restore")}
    device_id = "restore-device-id"
    # A legacy deleted device carries no recorded disabled_by (UNDEFINED), so restore
    # returns the caller's disabled_by verbatim - no config-entry reconciliation clears
    # a DEVICE value.
    device_registry._deleted_devices[device_id] = attr.evolve(
        _mock_deleted_device(device_id, mock_config_entry.entry_id, identifiers),
        disabled_by=UNDEFINED,
    )

    with pytest.raises(HomeAssistantError, match=match):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers=identifiers,
            disabled_by=dr.DeviceEntryDisabler.DEVICE,
        )

    # Nothing was restored: no main device exists and the deleted entry is untouched
    assert len(device_registry.devices) == 0
    assert device_id in device_registry._deleted_devices
    assert device_registry._deleted_devices[device_id].disabled_by is UNDEFINED


@pytest.mark.usefixtures("hass")
async def test_child_device_update_identifiers(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting child device identifiers with new_identifiers, incl. collisions."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    # new_identifiers replaces the child device's identifiers
    updated = device_registry.async_update_child_device(
        child_device.id,
        new_identifiers={("test", "strip_outlet_1"), ("test", "strip_outlet_1_alias")},
    )
    assert updated.identifiers == {
        ("test", "strip_outlet_1"),
        ("test", "strip_outlet_1_alias"),
    }

    updated = device_registry.async_update_child_device(
        child_device.id, new_identifiers={("test", "strip_outlet_1")}
    )
    assert updated.identifiers == {("test", "strip_outlet_1")}

    with pytest.raises(HomeAssistantError, match="must have at least one identifier"):
        device_registry.async_update_child_device(
            child_device.id, new_identifiers=set()
        )

    # A child device can't take an identifier registered by a device (its parent)
    with pytest.raises(dr.DeviceIdentifierCollisionError):
        device_registry.async_update_child_device(
            child_device.id, new_identifiers={("test", "strip")}
        )

    # A device can't take an identifier registered by a child device
    with pytest.raises(dr.DeviceIdentifierCollisionError):
        device_registry.async_update_device(
            parent.id, merge_identifiers={("test", "strip_outlet_1")}
        )


@pytest.mark.usefixtures("hass")
async def test_child_device_get_or_create_rejects_invalid_identifier_count(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creating a child device with zero or multiple identifiers is rejected."""
    parent, _child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(dr.DeviceInfoError, match="must have at least one identifier"):
        device_registry.async_get_or_create_child(
            config_entry_id=mock_config_entry.entry_id,
            identifiers=set(),
            parent_device_id=parent.id,
            name="Outlet 1",
        )
    # The rejected registration leaves the existing child unchanged
    assert len(device_registry.child_devices) == 1


@pytest.mark.usefixtures("hass")
async def test_child_device_get_or_create_merges_identifiers(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test re-registering a child device merges additional identifiers into it.

    merge_identifiers is rejected on the public update path for a child device, so
    the internal merge only happens through async_get_or_create.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    merged = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1"), ("test", "strip_outlet_1_alias")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert merged.id == child_device.id
    assert merged.identifiers == {
        ("test", "strip_outlet_1"),
        ("test", "strip_outlet_1_alias"),
    }
    assert len(device_registry.child_devices) == 1


async def test_remove_parent_cascades_to_children(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing a parent device removes its child devices first."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    remove_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    device_registry.async_remove_device(parent.id)

    assert device_registry.async_get(parent.id) is None
    assert device_registry.async_get(child_device.id) is None
    assert not device_registry.child_devices
    assert child_device.id in device_registry._deleted_devices
    assert parent.id in device_registry._deleted_devices

    await hass.async_block_till_done()
    assert [event.data for event in remove_events] == [
        {
            "action": "remove",
            "device_id": child_device.id,
            "device": child_device.dict_repr,
        },
        {"action": "remove", "device_id": parent.id, "device": parent.dict_repr},
    ]


@pytest.mark.usefixtures("hass")
async def test_remove_child_device_and_restore(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing and restoring a child device preserves id and user data."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_child_device(
        child_device.id, area_id="garden", labels={"outdoor"}, name_by_user="Lamp"
    )

    device_registry.async_remove_device(child_device.id)
    assert device_registry.async_get(child_device.id) is None
    assert device_registry.async_get(parent.id) is not None

    restored = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert restored.id == child_device.id
    assert restored.area_id == "garden"
    assert restored.labels == {"outdoor"}
    assert restored.name_by_user == "Lamp"
    assert restored.parent_device_id == parent.id


@pytest.mark.usefixtures("hass")
async def test_restore_child_deleted_via_parent_cascade(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test restoring a child that was cascade-deleted with its parent.

    Removing the parent cascade-deletes the child; re-registering the parent and then
    the child restores the child with its id and user-provided data intact.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_child_device(
        child_device.id, area_id="garden", labels={"outdoor"}, name_by_user="Lamp"
    )

    device_registry.async_remove_device(parent.id)
    assert device_registry.async_get(child_device.id) is None
    assert child_device.id in device_registry._deleted_devices
    assert parent.id in device_registry._deleted_devices

    restored_parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    assert restored_parent.id == parent.id

    restored_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=restored_parent.id,
        name="Outlet 1",
    )
    assert restored_child.id == child_device.id
    assert restored_child.area_id == "garden"
    assert restored_child.labels == {"outdoor"}
    assert restored_child.name_by_user == "Lamp"
    assert restored_child.parent_device_id == restored_parent.id
    assert device_registry.async_get(child_device.id) is restored_child
    assert child_device.id not in device_registry._deleted_devices


@pytest.mark.usefixtures("hass")
async def test_parent_disable_cascades_to_children(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabling and enabling a parent device cascades to its children."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_child is not None
    assert updated_child.disabled_by is dr.DeviceEntryDisabler.DEVICE

    device_registry.async_update_device(parent.id, disabled_by=None)
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_child is not None
    assert updated_child.disabled_by is None


@pytest.mark.usefixtures("hass")
async def test_parent_enable_keeps_user_disabled_child(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test enabling a parent does not enable a user-disabled child device."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_child_device(
        child_device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    device_registry.async_update_device(parent.id, disabled_by=None)

    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_child is not None
    assert updated_child.disabled_by is dr.DeviceEntryDisabler.USER


@pytest.mark.usefixtures("hass")
async def test_child_device_disabled_by_reconciled_with_parent(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a child device's disabled_by is reconciled with the parent state."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    # DEVICE on a child of an enabled parent is inconsistent and ignored
    updated = device_registry.async_update_child_device(
        child_device.id, disabled_by=dr.DeviceEntryDisabler.DEVICE
    )
    assert updated.disabled_by is None
    assert "whose parent device is enabled" in caplog.text

    # A child of a disabled parent can't be enabled; it stays disabled by the parent
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    updated = device_registry.async_update_child_device(
        child_device.id, disabled_by=None
    )
    assert updated.disabled_by is dr.DeviceEntryDisabler.DEVICE
    assert "whose parent device is disabled" in caplog.text

    # A child device created under a disabled parent is born disabled
    new_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_2")},
        parent_device_id=parent.id,
        name="Outlet 2",
    )
    assert new_child.disabled_by is dr.DeviceEntryDisabler.DEVICE


async def test_config_entry_reenable_with_user_disabled_parent_no_warning(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test re-enabling a config entry with a user-disabled parent does not warn.

    The config-entry re-enable cascade clears the child's CONFIG_ENTRY disable by passing
    disabled_by=None; with the parent still user-disabled the child is coerced back to
    DEVICE. This internal reconciliation must not emit the "sets disabled_by to None"
    report, while a direct external enable of such a child must.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    disabled_parent = device_registry.async_get(parent.id)
    disabled_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert disabled_parent is not None
    assert disabled_child is not None
    assert disabled_parent.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert disabled_child.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    # User disables the parent while the config entry is disabled; the child keeps its
    # CONFIG_ENTRY disable because it is already disabled
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    child_after_parent_disable = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert child_after_parent_disable is not None
    assert child_after_parent_disable.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    caplog.clear()
    await hass.config_entries.async_set_disabled_by(mock_config_entry.entry_id, None)
    await hass.async_block_till_done()
    updated_parent = device_registry.async_get(parent.id)
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_parent is not None
    assert updated_child is not None
    assert updated_parent.disabled_by is dr.DeviceEntryDisabler.USER
    assert updated_child.disabled_by is dr.DeviceEntryDisabler.DEVICE
    assert "Detected code that" not in caplog.text

    # A direct external enable of the same child still warns, as it is not the cascade
    caplog.clear()
    updated = device_registry.async_update_child_device(
        child_device.id, disabled_by=None
    )
    assert updated.disabled_by is dr.DeviceEntryDisabler.DEVICE
    assert "whose parent device is disabled" in caplog.text


async def test_config_entry_disable_with_children(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabling and enabling a config entry cascades to child devices."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    updated_parent = device_registry.async_get(parent.id)
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_parent is not None
    assert updated_child is not None
    assert updated_parent.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert updated_child.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY

    await hass.config_entries.async_set_disabled_by(mock_config_entry.entry_id, None)
    await hass.async_block_till_done()
    updated_parent = device_registry.async_get(parent.id)
    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_parent is not None
    assert updated_child is not None
    assert updated_parent.disabled_by is None
    assert updated_child.disabled_by is None


async def test_disable_child_device_directly_disables_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test disabling a child device directly disables and re-enables its entities."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    entity_entry = entity_registry.async_get_or_create(
        "switch",
        "test",
        "outlet_1",
        config_entry=mock_config_entry,
        device_id=child_device.id,
    )

    device_registry.async_update_child_device(
        child_device.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    await hass.async_block_till_done()

    updated_entity = entity_registry.async_get(entity_entry.entity_id)
    assert updated_entity is not None
    assert updated_entity.disabled_by is er.RegistryEntryDisabler.DEVICE

    device_registry.async_update_child_device(child_device.id, disabled_by=None)
    await hass.async_block_till_done()

    updated_entity = entity_registry.async_get(entity_entry.entity_id)
    assert updated_entity is not None
    assert updated_entity.disabled_by is None


async def test_move_parent_with_children_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a parent device with child devices can't move."""
    other_entry = MockConfigEntry(title=None)
    other_entry.add_to_hass(hass)
    parent, _ = _create_parent_and_child(device_registry, mock_config_entry.entry_id)

    with pytest.raises(HomeAssistantError, match="has child devices"):
        device_registry.async_update_device(
            parent.id, new_config_entry_id=other_entry.entry_id
        )

    # The rejected move leaves the parent and its child untouched
    unchanged_parent = device_registry.async_get(parent.id)
    assert unchanged_parent is not None
    assert unchanged_parent.config_entry_id == mock_config_entry.entry_id
    assert len(device_registry.child_devices) == 1


async def test_convert_device_to_child_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test converting an already-split device to a child device keeps its id."""
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    old_split = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
        identifiers={("test", "strip_outlet_1")},
        manufacturer="acme",
        name="Outlet 1",
        via_device_id=parent.id,
    )
    device_registry.async_update_device(
        old_split.id, area_id="garden", name_by_user="Lamp"
    )
    # A new setup session: the split device is no longer live, so the integration
    # can now adopt it as a child device.
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    converted = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert isinstance(converted, dr.ChildDeviceEntry)
    assert converted.id == old_split.id
    assert converted.parent_device_id == parent.id
    assert converted.area_id == "garden"
    assert converted.name_by_user == "Lamp"
    assert converted.identifiers == {("test", "strip_outlet_1")}
    assert len(device_registry.devices) == 1
    assert len(device_registry.child_devices) == 1

    await hass.async_block_till_done()
    assert [event.data for event in update_events] == [
        {
            "action": "update",
            "device_id": old_split.id,
            "changes": {
                "connections": {(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
                "manufacturer": "acme",
                "parent_device_id": None,
                "via_device_id": parent.id,
            },
        },
    ]


@pytest.mark.parametrize(
    ("identifiers", "error"),
    [
        pytest.param(
            {("test", "other")},
            "can't be its own parent",
            id="self_parent",
        ),
        pytest.param(
            {("test", "strip")},
            "has child devices itself",
            id="has_children",
        ),
    ],
)
@pytest.mark.usefixtures("hass")
async def test_convert_device_to_child_device_errors(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    identifiers: set[tuple[str, str]],
    error: str,
) -> None:
    """Test invalid device to child device conversions."""
    _create_parent_and_child(device_registry, mock_config_entry.entry_id)
    other = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "other")},
        name="Other",
    )

    with pytest.raises(dr.DeviceInfoError, match=error):
        device_registry.async_get_or_create_child(
            config_entry_id=mock_config_entry.entry_id,
            identifiers=identifiers,
            parent_device_id=other.id,
            name="Nope",
        )

    # The conversion guards run before any reconcile, so the rejection mutates nothing
    assert len(device_registry.devices) == 2
    assert len(device_registry.child_devices) == 1
    assert device_registry.async_get(other.id) is other


@pytest.mark.parametrize(
    "identifiers",
    [
        pytest.param({("test", "strip_outlet_1")}, id="exact_identifiers"),
        pytest.param(
            {("test", "strip_outlet_1"), ("test", "strip_outlet_1_alias")},
            id="extra_identifiers",
        ),
    ],
)
@pytest.mark.usefixtures("hass")
async def test_link_device_info_matching_child_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    identifiers: set[tuple[str, str]],
) -> None:
    """Test a bare-identifier device info matching a child device raises."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(dr.DeviceInfoError, match="overlap with those of child device"):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers=identifiers,
        )

    # The child device is left untouched: not converted, no new device created
    assert len(device_registry.devices) == 1
    assert len(device_registry.child_devices) == 1
    assert (
        device_registry.async_get(child_device.id, include_main_devices=False)
        == child_device
    )
    assert child_device.identifiers == {("test", "strip_outlet_1")}


@pytest.mark.usefixtures("hass")
async def test_convert_device_to_child_detaches_via_links(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test converting a device to a child detaches inbound via_device links."""
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    outlet = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "outlet")},
        name="Outlet",
        via_device_id=parent.id,
    )
    nested = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "nested")},
        name="Nested",
        via_device_id=outlet.id,
    )
    assert nested.via_device_id == outlet.id
    # A new setup session: the outlet is no longer live and can be adopted as a child
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)

    converted = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "outlet")},
        parent_device_id=parent.id,
        name="Outlet",
    )
    assert isinstance(converted, dr.ChildDeviceEntry)
    assert converted.id == outlet.id

    # The inbound via link is detached so it can no longer resolve to a child device
    nested_after = device_registry.async_get_device(identifiers={("test", "nested")})
    assert nested_after is not None
    assert nested_after.via_device_id is None
    # No live device links to a child device through via_device_id
    child_via_targets = [
        device.id
        for device in device_registry.devices
        if device.via_device_id is not None
        and device_registry.async_get(device.via_device_id, include_main_devices=False)
        is not None
    ]
    assert child_via_targets == []


@pytest.mark.usefixtures("hass")
async def test_convert_device_to_child_same_session_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test registering a live device's identifiers as a child raises."""
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        name="Outlet 1",
    )

    with pytest.raises(
        dr.DeviceInfoError,
        match="registered as a device and as a child device",
    ):
        device_registry.async_get_or_create_child(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "strip_outlet_1")},
            parent_device_id=parent.id,
            name="Outlet 1",
        )

    # The conversion guard runs before any reconcile, so the rejection leaves the
    # device a main device and creates no child device
    assert device_registry.async_get(device.id) is device
    assert not device_registry.child_devices
    assert len(device_registry.devices) == 2


@pytest.mark.usefixtures("hass")
async def test_primary_device_info_matching_child_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a primary device info whose identifiers belong to a child raises."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(dr.DeviceInfoError, match="overlap with those of child device"):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "strip_outlet_1")},
            manufacturer="acme",
            name="Outlet 1",
        )

    # The rejection leaves the child device untouched and creates no main device for
    # its identifiers
    assert (
        device_registry.async_get(child_device.id, include_main_devices=False)
        is child_device
    )
    assert len(device_registry.child_devices) == 1
    assert len(device_registry.devices) == 1


@pytest.mark.usefixtures("hass")
async def test_get_or_create_via_device_id_naming_child_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a via_device_id resolving to a child device is rejected before mutation."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(
        dr.DeviceInfoError,
        match="is a child device, which can't be a via device",
    ):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "new_device")},
            via_device_id=child_device.id,
        )

    # Validation precedes mutation, so the rejected device is not partially created
    assert (
        device_registry.async_get_device(identifiers={("test", "new_device")}) is None
    )
    assert len(device_registry.devices) == 1

    # The deprecated via_device (identifier form) resolves against main devices only, so
    # a child's identifier is treated as an unknown via device: it logs a deprecation and
    # links nothing rather than raising. Only the id form enforces the invariant.
    linked = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "new_device")},
        via_device=("test", "strip_outlet_1"),
    )
    assert linked.via_device_id is None


@pytest.mark.usefixtures("hass")
async def test_update_device_via_device_id_naming_child_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test updating via_device_id to a child device raises, leaving it unchanged."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "device")},
        name="Device",
    )

    with pytest.raises(
        HomeAssistantError,
        match="is a child device, which can't be a via device",
    ):
        device_registry.async_update_device(device.id, via_device_id=child_device.id)

    assert device_registry.async_get(device.id).via_device_id is None


@pytest.mark.usefixtures("hass")
async def test_deleted_device_restored_as_child_device(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a deleted device can restore as a child device and vice versa."""
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        name="Outlet 1",
        manufacturer="acme",
    )
    device_registry.async_update_device(device.id, area_id="garden")
    device_registry.async_remove_device(device.id)

    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    restored_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert isinstance(restored_child, dr.ChildDeviceEntry)
    assert restored_child.id == device.id
    assert restored_child.area_id == "garden"

    # And a deleted child device can restore as a device
    device_registry.async_remove_device(restored_child.id)
    restored_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        name="Outlet 1",
        manufacturer="acme",
    )
    assert isinstance(restored_device, dr.DeviceEntry)
    assert restored_device.id == device.id
    assert restored_device.area_id == "garden"


async def test_child_device_orphan_restore(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a child device orphaned by config entry removal restores."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_child_device(child_device.id, area_id="garden")

    device_registry.async_clear_config_entry(mock_config_entry.entry_id)
    assert not device_registry._devices
    assert not device_registry.child_devices

    new_entry = MockConfigEntry(title=None)
    new_entry.add_to_hass(hass)
    new_parent = device_registry.async_get_or_create(
        config_entry_id=new_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    restored = device_registry.async_get_or_create_child(
        config_entry_id=new_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=new_parent.id,
        name="Outlet 1",
    )
    assert restored.id == child_device.id
    assert restored.area_id == "garden"
    assert restored.config_entry_id == new_entry.entry_id


async def test_child_device_load_and_save(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test child devices round-trip through the store, unchanged on re-save."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_child_device(
        child_device.id, area_id="garden", labels={"outdoor"}, name_by_user="Lamp"
    )

    registry2 = dr.DeviceRegistry(hass)
    await flush_store(device_registry._store)
    first_save = deepcopy(hass_storage[dr.STORAGE_KEY]["data"])
    await registry2.async_load()

    assert list(device_registry._devices) == list(registry2._devices)
    assert list(device_registry.child_devices) == list(registry2.child_devices)
    loaded_child = registry2.async_get(child_device.id, include_main_devices=False)
    assert loaded_child is not None
    assert loaded_child.parent_device_id == parent.id
    assert loaded_child.area_id == "garden"
    assert loaded_child.labels == {"outdoor"}
    assert loaded_child.name_by_user == "Lamp"
    assert loaded_child.identifiers == {("test", "strip_outlet_1")}

    # Loading must not silently mutate a child device, so re-saving the freshly
    # loaded registry reproduces the same stored data.
    registry2.async_schedule_save()
    await flush_store(registry2._store)
    assert hass_storage[dr.STORAGE_KEY]["data"] == first_save


async def test_child_device_stored_fragment(
    hass_storage: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    mock_config_entry_with_subentries: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the exact serialized payload of a non-empty stored child device.

    Pins the full key set so an extra serialized key can't slip in unnoticed.
    """
    freezer.move_to("2024-01-01T00:00:00+00:00")
    entry_id = mock_config_entry_with_subentries.entry_id
    parent, child_device = _create_parent_and_child(
        device_registry, entry_id, config_subentry_id="mock-subentry-id-1-1"
    )
    device_registry.async_update_child_device(
        child_device.id,
        area_id="garden",
        disabled_by=dr.DeviceEntryDisabler.USER,
        labels={"outdoor"},
        name_by_user="Lamp",
    )

    await flush_store(device_registry._store)

    assert hass_storage[dr.STORAGE_KEY]["data"]["child_devices"] == [
        {
            "area_id": "garden",
            "config_entry_id": entry_id,
            "config_subentry_id": "mock-subentry-id-1-1",
            "created_at": "2024-01-01T00:00:00+00:00",
            "disabled_by": "user",
            "id": child_device.id,
            "identifiers": [["test", "strip_outlet_1"]],
            "labels": ["outdoor"],
            "modified_at": "2024-01-01T00:00:00+00:00",
            "name_by_user": "Lamp",
            "name": "Outlet 1",
            "parent_device_id": parent.id,
        }
    ]


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_3_3_to_3_4(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration from 3.3 adds the child devices list."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 3,
        "minor_version": 3,
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
                    "connections": [],
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["test", "strip"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": "Power strip",
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
    assert not registry.child_devices

    await flush_store(registry._store)
    assert hass_storage[dr.STORAGE_KEY]["minor_version"] == 4
    assert hass_storage[dr.STORAGE_KEY]["data"]["child_devices"] == []


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_child_device_with_missing_parent(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a stored child device without its parent is dropped with an error."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [],
            "child_devices": [
                {
                    "area_id": None,
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "id": "childdeviceid",
                    "identifiers": [["test", "strip_outlet_1"]],
                    "labels": [],
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": "Outlet 1",
                    "parent_device_id": "missingparent",
                }
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    assert not registry.child_devices
    assert "Dropping child device childdeviceid" in caplog.text

    # The drop scheduled a save, so it persists instead of leaving the store dirty
    # until an unrelated write
    await flush_store(registry._store)
    assert hass_storage[dr.STORAGE_KEY]["data"]["child_devices"] == []


async def test_effective_area_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test effective area resolution for devices and child devices."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert dr.async_get_effective_area_id(hass, parent) is None
    assert dr.async_get_effective_area_id(hass, child_device) is None

    # The child inherits the parent's area, resolved at read time
    updated_parent = device_registry.async_update_device(parent.id, area_id="garage")
    child_device = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert dr.async_get_effective_area_id(hass, child_device) == "garage"

    # An explicitly set area overrides the inherited one
    child_device = device_registry.async_update_child_device(
        child_device.id, area_id="garden"
    )
    assert dr.async_get_effective_area_id(hass, child_device) == "garden"

    # A parent area change is reflected immediately for inheriting children
    child_device = device_registry.async_update_child_device(
        child_device.id, area_id=None
    )
    device_registry.async_update_device(updated_parent.id, area_id="attic")
    assert dr.async_get_effective_area_id(hass, child_device) == "attic"


@pytest.mark.usefixtures("hass")
async def test_entries_for_area_with_child_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test area queries include child devices by effective area."""
    parent, inheriting_child = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    overriding_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_2")},
        parent_device_id=parent.id,
        name="Outlet 2",
    )
    device_registry.async_update_device(parent.id, area_id="garage")
    device_registry.async_update_child_device(overriding_child.id, area_id="garden")

    parent = device_registry.async_get(parent.id)
    inheriting_child = device_registry.async_get(
        inheriting_child.id, include_main_devices=False
    )
    overriding_child = device_registry.async_get(
        overriding_child.id, include_main_devices=False
    )

    assert dr.async_entries_for_area(device_registry, "garage") == [
        parent,
        inheriting_child,
    ]
    assert dr.async_entries_for_area(device_registry, "garden") == [overriding_child]


@pytest.mark.usefixtures("hass")
async def test_clear_area_id_with_child_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test deleting an area clears explicitly set child device areas."""
    parent, inheriting_child = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_device(parent.id, area_id="garage")
    device_registry.async_update_child_device(inheriting_child.id, area_id="garage")

    device_registry.async_clear_area_id("garage")

    updated_parent = device_registry.async_get(parent.id)
    updated_child = device_registry.async_get(
        inheriting_child.id, include_main_devices=False
    )
    assert updated_parent is not None
    assert updated_child is not None
    assert updated_parent.area_id is None
    assert updated_child.area_id is None


@pytest.mark.usefixtures("hass")
async def test_clear_label_id_with_child_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test deleting a label removes it from child devices."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_child_device(
        child_device.id, labels={"outdoor", "xmas"}
    )

    device_registry.async_clear_label_id("xmas")

    updated_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert updated_child is not None
    assert updated_child.labels == {"outdoor"}


@pytest.mark.usefixtures("hass")
async def test_entries_for_label_includes_child_devices(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test label queries include child devices carrying the label."""
    parent, labeled_child = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    unlabeled_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_2")},
        parent_device_id=parent.id,
        name="Outlet 2",
    )
    parent = device_registry.async_update_device(parent.id, labels={"label1"})
    labeled_child = device_registry.async_update_child_device(
        labeled_child.id, labels={"label1"}
    )

    entries = dr.async_entries_for_label(device_registry, "label1")
    assert len(entries) == 2
    assert parent in entries
    assert labeled_child in entries
    # Labels are never inherited, so a child without the label is excluded even though
    # its parent carries it
    assert unlabeled_child not in entries


async def test_async_cleanup_removes_child_device_with_missing_parent(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test cleanup removes a child device whose parent is gone."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    # Simulate store corruption: drop the parent without the remove cascade
    del device_registry._devices[parent.id]

    dr.async_cleanup(hass, device_registry, entity_registry)

    assert (
        device_registry.async_get(child_device.id, include_main_devices=False) is None
    )
    assert "Removing child device" in caplog.text

    # The removal scheduled a save, so the drop persists instead of leaving the store
    # dirty until an unrelated write
    await flush_store(device_registry._store)
    assert hass_storage[dr.STORAGE_KEY]["data"]["child_devices"] == []


@pytest.mark.parametrize("load_registries", [False])
async def test_async_cleanup_removes_child_device_with_stale_config_entry(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test cleanup removes a stored child device whose config entry no longer exists.

    A child device shares its parent's config entry, but a corrupt store can pair a
    valid parent with a child naming a config entry that no longer exists. Load only
    guards against a missing parent, so the stale config entry is caught by cleanup.
    """
    hass_storage[dr.STORAGE_KEY] = {
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
                    "connections": [],
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "parentdeviceid",
                    "identifiers": [["test", "strip"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": "Power strip",
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "child_devices": [
                {
                    "area_id": None,
                    "config_entry_id": "stale-config-entry-id",
                    "config_subentry_id": None,
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "id": "childdeviceid",
                    "identifiers": [["test", "strip_outlet_1"]],
                    "labels": [],
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": "Outlet 1",
                    "parent_device_id": "parentdeviceid",
                }
            ],
            "deleted_devices": [],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    # The child loads because its parent is present; the stale config entry is only
    # caught by the cleanup sweep below
    assert registry.async_get("childdeviceid", include_main_devices=False) is not None

    entity_registry = er.EntityRegistry(hass)
    await entity_registry.async_load()
    dr.async_cleanup(hass, registry, entity_registry)

    assert registry.async_get("childdeviceid", include_main_devices=False) is None
    assert "its config entry stale-config-entry-id no longer exists" in caplog.text

    # The parent, on a valid config entry, is left untouched
    assert registry.async_get("parentdeviceid") is not None

    # The removal scheduled a save, so the drop persists
    await flush_store(registry._store)
    assert hass_storage[dr.STORAGE_KEY]["data"]["child_devices"] == []


@pytest.mark.usefixtures("hass")
async def test_device_info_with_connections_matching_child_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device info with connections claiming a child's identifier raises.

    Child device identifier collisions are always rejected, even for a stale child
    and even when the device info carries connections.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    # A new setup session: the child device is stale, but is still not adopted
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)

    with pytest.raises(dr.DeviceInfoError, match="overlap with those of child device"):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")},
            identifiers={("test", "strip_outlet_1")},
            name="Not an outlet",
        )

    # The rejection leaves the child device untouched and creates no main device
    assert (
        device_registry.async_get(child_device.id, include_main_devices=False)
        is child_device
    )
    assert len(device_registry.child_devices) == 1
    assert len(device_registry.devices) == 1


@pytest.mark.usefixtures("hass")
async def test_live_child_device_identifier_collision_raises(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device colliding with a live child device raises."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    hub = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "hub")},
        name="Hub",
    )
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    # A device matched by its own identifier that also claims a live child's identifier
    # collides with the child and is rejected
    with pytest.raises(dr.DeviceInfoError, match="overlap with those of child device"):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "hub"), ("test", "strip_outlet_1")},
            name="Hub",
        )

    # The raise precedes reconciliation, so nothing changed
    unchanged_child = device_registry.async_get(child_device.id)
    assert isinstance(unchanged_child, dr.ChildDeviceEntry)
    assert unchanged_child is child_device
    assert unchanged_child.parent_device_id == parent.id
    assert unchanged_child.identifiers == {("test", "strip_outlet_1")}
    assert device_registry.async_get(hub.id) is hub
    assert len(device_registry.devices) == 2
    assert len(device_registry.child_devices) == 1
    await hass.async_block_till_done()
    assert len(update_events) == 0


async def test_child_and_main_device_same_identifier_across_entries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a child and a main device in different entries can share an identifier.

    Identifiers are unique only within a config entry, so a child device in one entry
    coexists with a main device of another entry sharing its identifier, each resolvable
    in its own namespace.
    """
    entry_a = mock_config_entry
    _, child_device = _create_parent_and_child(device_registry, entry_a.entry_id)

    entry_b = MockConfigEntry(title=None)
    entry_b.add_to_hass(hass)
    main_device = device_registry.async_get_or_create(
        config_entry_id=entry_b.entry_id,
        identifiers={("test", "strip_outlet_1")},
        name="Standalone outlet",
    )

    assert isinstance(main_device, dr.DeviceEntry)
    assert main_device.id != child_device.id
    assert len(device_registry.devices) == 2
    assert len(device_registry.child_devices) == 1

    # The shared identifier resolves to the child in entry A and the main device in B
    assert (
        device_registry.async_get_child_device_by_identifier(
            ("test", "strip_outlet_1"), entry_a.entry_id
        )
        is child_device
    )
    assert (
        device_registry.async_get_child_device_by_identifier(
            ("test", "strip_outlet_1"), entry_b.entry_id
        )
        is None
    )
    assert (
        device_registry.async_get_device_by_identifier(
            ("test", "strip_outlet_1"), entry_b.entry_id
        )
        is main_device
    )
    assert (
        device_registry.async_get_device_by_identifier(
            ("test", "strip_outlet_1"), entry_a.entry_id
        )
        is None
    )


@pytest.mark.usefixtures("hass")
async def test_child_device_config_entry_compat_shims(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the deprecated config-entry compatibility shims on a child device entry.

    A child device is keyed by a single config entry and subentry; the deprecated
    multi-entry shims inherited from BaseDeviceEntry report that single membership.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    assert child_device.config_entries == {mock_config_entry.entry_id}
    assert child_device.config_entries_subentries == {
        mock_config_entry.entry_id: {None}
    }
    assert child_device.primary_config_entry == mock_config_entry.entry_id


@pytest.mark.usefixtures("hass")
async def test_deleted_child_device_restored_as_device_clears_device_disable(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test restoring a device-disabled deleted child as a full device clears it.

    A child disabled by its parent (DeviceEntryDisabler.DEVICE) keeps that disable as a
    deleted device; restoring its identifiers as a full device, which has no parent,
    drops the parent-device disable.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    disabled_child = device_registry.async_get(
        child_device.id, include_main_devices=False
    )
    assert disabled_child is not None
    assert disabled_child.disabled_by is dr.DeviceEntryDisabler.DEVICE

    device_registry.async_remove_device(child_device.id)

    restored_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        manufacturer="acme",
        name="Outlet 1",
    )
    assert isinstance(restored_device, dr.DeviceEntry)
    assert restored_device.id == child_device.id
    assert restored_device.disabled_by is None


@pytest.mark.usefixtures("hass")
async def test_deleted_device_disabled_restored_as_child_rederives_disable(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device-disabled deleted device re-derives its disable when restored.

    The stored DeviceEntryDisabler.DEVICE is recomputed from the (now-enabled) parent
    on restore, so the restored child is enabled.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    device_registry.async_remove_device(child_device.id)
    device_registry.async_update_device(parent.id, disabled_by=None)

    restored = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert isinstance(restored, dr.ChildDeviceEntry)
    assert restored.id == child_device.id
    assert restored.disabled_by is None


@pytest.mark.usefixtures("hass")
async def test_deleted_device_restored_as_child_of_disabled_parent(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test restoring a deleted device as a child of a disabled parent disables it."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_remove_device(child_device.id)
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )

    restored = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert restored.id == child_device.id
    assert restored.disabled_by is dr.DeviceEntryDisabler.DEVICE


async def test_deleted_device_restored_as_child_under_disabled_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test restoring a deleted device as a child under a disabled config entry."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry.async_remove_device(child_device.id)

    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    restored = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert restored.id == child_device.id
    assert restored.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY


async def test_config_entry_disabled_deleted_device_restored_as_child(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config-entry-disabled deleted device restores as an enabled child.

    The stored DeviceEntryDisabler.CONFIG_ENTRY is cleared because the config entry is
    enabled again by the time the device restores as a child.
    """
    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        manufacturer="acme",
        name="Outlet 1",
    )
    assert device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    device_registry.async_remove_device(device.id)

    await hass.config_entries.async_set_disabled_by(mock_config_entry.entry_id, None)
    await hass.async_block_till_done()

    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    restored = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert restored.id == device.id
    assert restored.disabled_by is None


@pytest.mark.parametrize("load_registries", [False])
async def test_legacy_undefined_disabled_deleted_device_restored_as_child(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test restoring a legacy deleted device (disabled_by undefined) as a child.

    A deleted device stored before disabled_by was tracked loads with an undefined
    disable; restoring it as a child resolves that to None.
    """
    hass_storage[dr.STORAGE_KEY] = {
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
                    "connections": [],
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "entry_type": None,
                    "hw_version": None,
                    "id": "parentdeviceid",
                    "identifiers": [["test", "strip"]],
                    "labels": [],
                    "manufacturer": None,
                    "model": None,
                    "model_id": None,
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "name": "Power strip",
                    "primary_config_entry": mock_config_entry.entry_id,
                    "serial_number": None,
                    "sw_version": None,
                    "via_device_id": None,
                }
            ],
            "child_devices": [],
            "deleted_devices": [
                {
                    "area_id": None,
                    "config_entry_id": mock_config_entry.entry_id,
                    "config_subentry_id": None,
                    "connections": [],
                    "created_at": "2024-01-01T00:00:00+00:00",
                    "disabled_by": None,
                    "disabled_by_undefined": True,
                    "id": "outletdeviceid",
                    "identifiers": [["test", "strip_outlet_1"]],
                    "labels": [],
                    "modified_at": "2024-01-01T00:00:00+00:00",
                    "name_by_user": None,
                    "orphaned_timestamp": None,
                    "domain": None,
                }
            ],
        },
    }

    dr.async_setup(hass)
    await dr.async_load(hass)
    registry = dr.async_get(hass)

    restored = registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id="parentdeviceid",
        name="Outlet 1",
    )
    assert isinstance(restored, dr.ChildDeviceEntry)
    assert restored.id == "outletdeviceid"
    assert restored.disabled_by is None


@pytest.mark.usefixtures("hass")
async def test_convert_device_to_child_subentry_mismatch(
    device_registry: dr.DeviceRegistry,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test converting a device to a child rejects a config subentry mismatch."""
    entry_id = mock_config_entry_with_subentries.entry_id
    parent = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id="mock-subentry-id-1-1",
        identifiers={("test", "strip")},
        name="Power strip",
    )
    device = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id="mock-subentry-id-1-2",
        identifiers={("test", "strip_outlet_1")},
        name="Outlet 1",
    )

    with pytest.raises(dr.DeviceInfoError, match="same config subentry"):
        device_registry.async_get_or_create_child(
            config_entry_id=entry_id,
            config_subentry_id="mock-subentry-id-1-1",
            identifiers={("test", "strip_outlet_1")},
            parent_device_id=parent.id,
            name="Outlet 1",
        )

    # The conversion guard runs before any reconcile, so the device is untouched
    assert device_registry.async_get(device.id) is device
    assert not device_registry.child_devices


async def test_convert_device_with_composite_identifiers_to_child(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test converting a composite-split device to a child replaces its identifiers.

    Identifiers copied from a pre-migration composite are replaced, not merged, so the
    extra composite identifier is dropped.
    """
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1"), ("test", "strip_outlet_1_stale")},
        name="Outlet 1",
        via_device_id=parent.id,
    )
    device_registry._async_update_device(device.id, has_composite_identifiers=True)
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    converted = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert isinstance(converted, dr.ChildDeviceEntry)
    assert converted.id == device.id
    assert converted.identifiers == {("test", "strip_outlet_1")}

    await hass.async_block_till_done()
    # The conversion reports the replaced identifiers as the old value
    assert update_events[0].data["changes"]["identifiers"] == {
        ("test", "strip_outlet_1"),
        ("test", "strip_outlet_1_stale"),
    }


async def test_convert_device_to_child_of_disabled_parent(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test converting a device to a child of a disabled parent disables the child."""
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    device_registry.async_update_device(
        parent.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        name="Outlet 1",
        via_device_id=parent.id,
    )
    assert device.disabled_by is None
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)
    update_events = async_capture_events(hass, dr.EVENT_DEVICE_REGISTRY_UPDATED)

    converted = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert isinstance(converted, dr.ChildDeviceEntry)
    assert converted.id == device.id
    assert converted.disabled_by is dr.DeviceEntryDisabler.DEVICE

    await hass.async_block_till_done()
    assert update_events[0].data["changes"]["disabled_by"] is None


async def test_move_parent_with_pending_move_and_children_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test completing a deferred move of a parent with child devices is rejected."""
    other_entry = MockConfigEntry(title=None)
    other_entry.add_to_hass(hass)
    parent, _ = _create_parent_and_child(device_registry, mock_config_entry.entry_id)

    # Arm a deferred move of the parent to another config entry
    device_registry._async_update_device(
        parent.id, add_config_entry_id=other_entry.entry_id
    )

    # Completing the pending move by removing the current owner is rejected
    with pytest.raises(HomeAssistantError, match="has child devices"):
        device_registry._async_update_device(
            parent.id, remove_config_entry_id=mock_config_entry.entry_id
        )

    unchanged_parent = device_registry.async_get(parent.id)
    assert unchanged_parent is not None
    assert unchanged_parent.config_entry_id == mock_config_entry.entry_id
    assert len(device_registry.child_devices) == 1


@pytest.mark.usefixtures("hass")
async def test_update_child_device_both_identifier_args_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test defining both merge_identifiers and new_identifiers is rejected.

    Only the internal update path can pass both, so the private method is exercised.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    with pytest.raises(
        HomeAssistantError,
        match="Cannot define both merge_identifiers and new_identifiers",
    ):
        device_registry._async_update_child_device(
            child_device.id,
            merge_identifiers={("test", "a")},
            new_identifiers={("test", "b")},
        )


async def test_update_child_disabled_by_none_on_disabled_config_entry_reports(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enabling a child of a disabled config entry is ignored and reported."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    caplog.clear()
    updated = device_registry.async_update_child_device(
        child_device.id, disabled_by=None
    )
    assert updated.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    assert (
        "sets disabled_by to None on a child device belonging to the disabled "
        "config entry" in caplog.text
    )


@pytest.mark.usefixtures("hass")
async def test_update_child_disabled_by_config_entry_on_enabled_entry_reports(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test CONFIG_ENTRY disabling a child of an enabled config entry is ignored."""
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )

    updated = device_registry.async_update_child_device(
        child_device.id, disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY
    )
    assert updated.disabled_by is None
    assert (
        "sets disabled_by to DeviceEntryDisabler.CONFIG_ENTRY on a child device "
        "belonging to the enabled config entry" in caplog.text
    )


async def test_create_child_device_under_disabled_config_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a child device created under a disabled config entry is disabled by it."""
    await hass.config_entries.async_set_disabled_by(
        mock_config_entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()

    parent = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip")},
        name="Power strip",
    )
    assert parent.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY
    child_device = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_1")},
        parent_device_id=parent.id,
        name="Outlet 1",
    )
    assert child_device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY


@pytest.mark.usefixtures("hass")
async def test_recreate_child_clears_stale_config_entry_disable(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the create reconciliation clears a stale CONFIG_ENTRY disable.

    A child carrying a CONFIG_ENTRY disable while its config entry is enabled is an
    inconsistent leftover; the create-time (is_new) reconciliation clears it. The state
    is only reachable internally, so the private update path is exercised.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    device_registry._child_devices[child_device.id] = attr.evolve(
        device_registry.async_get(child_device.id, include_main_devices=False),
        disabled_by=dr.DeviceEntryDisabler.CONFIG_ENTRY,
    )

    result = device_registry._async_update_child_device(
        child_device.id, is_new=True, merge_identifiers=child_device.identifiers
    )
    assert result is not None
    assert result.disabled_by is None


@pytest.mark.usefixtures("hass")
async def test_update_child_identifiers_purges_colliding_deleted_device(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding an identifier to a child purges a colliding deleted device.

    A deleted device holding an identity the child now owns can never restore, so it is
    dropped.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    ghost = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "ghost")},
        name="Ghost",
    )
    device_registry.async_remove_device(ghost.id)
    assert ghost.id in device_registry._deleted_devices

    device_registry.async_update_child_device(
        child_device.id,
        new_identifiers={("test", "strip_outlet_1"), ("test", "ghost")},
    )
    assert ghost.id not in device_registry._deleted_devices


@pytest.mark.usefixtures("hass")
async def test_child_device_identifier_collision_with_other_child(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a child device can't take an identifier registered by another child."""
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    other_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_2")},
        parent_device_id=parent.id,
        name="Outlet 2",
    )

    with pytest.raises(dr.DeviceIdentifierCollisionError):
        device_registry.async_update_child_device(
            child_device.id, new_identifiers={("test", "strip_outlet_2")}
        )
    # The rejected update leaves both children unchanged
    assert (
        device_registry.async_get(other_child.id, include_main_devices=False)
        is other_child
    )


@pytest.mark.usefixtures("hass")
async def test_stale_child_device_identifier_collision_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device claiming a stale child's identifier raises.

    Child device identifier collisions are rejected regardless of whether the child
    was registered this setup session; stale children are never stripped or removed.
    """
    _, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    hub = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "hub")},
        name="Hub",
    )
    # A new setup session: every device of the config entry is now stale
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)

    with pytest.raises(dr.DeviceInfoError, match="overlap with those of child device"):
        device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "hub"), ("test", "strip_outlet_1")},
            name="Hub",
        )

    # The rejection leaves the child device and the hub untouched
    assert (
        device_registry.async_get(child_device.id, include_main_devices=False)
        is child_device
    )
    assert child_device.identifiers == {("test", "strip_outlet_1")}
    assert device_registry.async_get(hub.id) is hub
    assert hub.identifiers == {("test", "hub")}


@pytest.mark.usefixtures("hass")
async def test_get_or_create_child_identifier_owned_by_other_child_raises(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a child registration claiming another child's identifier raises.

    A registration spanning the identifiers of two children is rejected instead of
    merging them, even when the children are stale.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    other_child = device_registry.async_get_or_create_child(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("test", "strip_outlet_2")},
        parent_device_id=parent.id,
        name="Outlet 2",
    )
    # A new setup session: both children are stale
    device_registry.async_config_entry_unloaded(mock_config_entry.entry_id)

    with pytest.raises(dr.DeviceInfoError, match="already registered for child"):
        device_registry.async_get_or_create_child(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("test", "strip_outlet_1"), ("test", "strip_outlet_2")},
            parent_device_id=parent.id,
            name="Merged outlet",
        )

    # The rejection leaves both children untouched
    assert (
        device_registry.async_get(child_device.id, include_main_devices=False)
        is child_device
    )
    assert (
        device_registry.async_get(other_child.id, include_main_devices=False)
        is other_child
    )


@pytest.mark.usefixtures("hass")
async def test_clear_config_entry_removes_orphaned_child_device(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test clearing a config entry removes a child device orphaned by corruption.

    A child always shares its parent's config entry, so the parent cascade removes it;
    this defensive sweep only fires for a corrupt store. Deleting the parent from the
    live registry without the cascade reproduces that state.
    """
    parent, child_device = _create_parent_and_child(
        device_registry, mock_config_entry.entry_id
    )
    del device_registry._devices[parent.id]

    device_registry.async_clear_config_entry(mock_config_entry.entry_id)

    assert (
        device_registry.async_get(child_device.id, include_main_devices=False) is None
    )
    assert not device_registry.child_devices


@pytest.mark.usefixtures("hass")
async def test_clear_config_subentry_removes_orphaned_child_device(
    device_registry: dr.DeviceRegistry,
    mock_config_entry_with_subentries: MockConfigEntry,
) -> None:
    """Test clearing a config subentry removes only that subentry's orphaned children.

    A child always shares its parent's subentry, so the parent cascade removes it; this
    defensive sweep only fires for a corrupt store, and skips children in another
    subentry. Deleting the parents from the live registry reproduces that state.
    """
    entry_id = mock_config_entry_with_subentries.entry_id
    parent_1 = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id="mock-subentry-id-1-1",
        identifiers={("test", "strip_1")},
        name="Strip 1",
    )
    child_1 = device_registry.async_get_or_create_child(
        config_entry_id=entry_id,
        config_subentry_id="mock-subentry-id-1-1",
        identifiers={("test", "outlet_1")},
        parent_device_id=parent_1.id,
        name="Outlet 1",
    )
    parent_2 = device_registry.async_get_or_create(
        config_entry_id=entry_id,
        config_subentry_id="mock-subentry-id-1-2",
        identifiers={("test", "strip_2")},
        name="Strip 2",
    )
    child_2 = device_registry.async_get_or_create_child(
        config_entry_id=entry_id,
        config_subentry_id="mock-subentry-id-1-2",
        identifiers={("test", "outlet_2")},
        parent_device_id=parent_2.id,
        name="Outlet 2",
    )
    del device_registry._devices[parent_1.id]
    del device_registry._devices[parent_2.id]

    device_registry.async_clear_config_subentry(entry_id, "mock-subentry-id-1-1")

    # The child in the cleared subentry is removed, the one in the other subentry kept
    assert device_registry.async_get(child_1.id, include_main_devices=False) is None
    assert device_registry.async_get(child_2.id, include_main_devices=False) is not None
