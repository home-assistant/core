"""Tests for the Device Registry."""
from contextlib import nullcontext
import time
from typing import Any
from unittest.mock import patch

import pytest
from yarl import URL

from homeassistant import config_entries
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)

from tests.common import MockConfigEntry, flush_store


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, async_capture)

    return events


async def test_get_or_create_returns_same_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    update_events,
) -> None:
    """Make sure we do not duplicate entries."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:66:77:88")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="1234",
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
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[1]["changes"] == {
        "connections": {("mac", "12:34:56:ab:cd:ef")}
    }


async def test_requirement_for_identifier_or_connection(
    device_registry: dr.DeviceRegistry,
) -> None:
    """Make sure we do require some descriptor of device."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers=set(),
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id="1234",
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
            config_entry_id="1234",
            connections=set(),
            identifiers=set(),
            manufacturer="manufacturer",
            model="model",
        )


async def test_multiple_config_entries(device_registry: dr.DeviceRegistry) -> None:
    """Make sure we do not get duplicate entries."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id="456",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry2.config_entries == {"123", "456"}


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading stored devices on start."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": dr.STORAGE_VERSION_MAJOR,
        "minor_version": dr.STORAGE_VERSION_MINOR,
        "data": {
            "devices": [
                {
                    "area_id": "12345A",
                    "config_entries": ["1234"],
                    "configuration_url": "https://example.com/config",
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": dr.DeviceEntryDisabler.USER,
                    "entry_type": dr.DeviceEntryType.SERVICE,
                    "hw_version": "hw_version",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name_by_user": "Test Friendly Name",
                    "name": "name",
                    "sw_version": "version",
                    "via_device_id": None,
                }
            ],
            "deleted_devices": [
                {
                    "config_entries": ["1234"],
                    "connections": [["Zigbee", "23.45.67.89.01"]],
                    "id": "bcdefghijklmn",
                    "identifiers": [["serial", "34:56:AB:CD:EF:12"]],
                    "orphaned_timestamp": None,
                }
            ],
        },
    }

    await dr.async_load(hass)
    registry = dr.async_get(hass)
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 1

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "12:34:56:AB:CD:EF")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry == dr.DeviceEntry(
        area_id="12345A",
        config_entries={"1234"},
        configuration_url="https://example.com/config",
        connections={("Zigbee", "01.23.45.67.89")},
        disabled_by=dr.DeviceEntryDisabler.USER,
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version",
        id="abcdefghijklm",
        identifiers={("serial", "12:34:56:AB:CD:EF")},
        manufacturer="manufacturer",
        model="model",
        name_by_user="Test Friendly Name",
        name="name",
        suggested_area=None,  # Not stored
        sw_version="version",
    )
    assert isinstance(entry.config_entries, set)
    assert isinstance(entry.connections, set)
    assert isinstance(entry.identifiers, set)

    # Restore a device, id should be reused from the deleted device entry
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("Zigbee", "23.45.67.89.01")},
        identifiers={("serial", "34:56:AB:CD:EF:12")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry == dr.DeviceEntry(
        config_entries={"1234"},
        connections={("Zigbee", "23.45.67.89.01")},
        id="bcdefghijklmn",
        identifiers={("serial", "34:56:AB:CD:EF:12")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.id == "bcdefghijklmn"
    assert isinstance(entry.config_entries, set)
    assert isinstance(entry.connections, set)
    assert isinstance(entry.identifiers, set)


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_1_to_1_3(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.1 to 1.3."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "data": {
            "devices": [
                {
                    "config_entries": ["1234"],
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "entry_type": "service",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "sw_version": "version",
                },
                # Invalid entry type
                {
                    "config_entries": [None],
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
                    "identifiers": [["serial", "12:34:56:AB:CD:FF"]],
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
        config_entry_id="1234",
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "12:34:56:AB:CD:EF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "12:34:56:AB:CD:EF")},
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
                    "config_entries": ["1234"],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": [None],
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
            "deleted_devices": [
                {
                    "config_entries": ["123456"],
                    "connections": [],
                    "id": "deletedid",
                    "identifiers": [["serial", "12:34:56:AB:CD:FF"]],
                    "orphaned_timestamp": None,
                }
            ],
        },
    }


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_1_2_to_1_3(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.2 to 1.3."""
    hass_storage[dr.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "key": dr.STORAGE_KEY,
        "data": {
            "devices": [
                {
                    "area_id": None,
                    "config_entries": ["1234"],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "sw_version": "version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": [None],
                    "configuration_url": None,
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": None,
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
        config_entry_id="1234",
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "12:34:56:AB:CD:EF")},
    )
    assert entry.id == "abcdefghijklm"

    # Update to trigger a store
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "12:34:56:AB:CD:EF")},
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
                    "config_entries": ["1234"],
                    "configuration_url": None,
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "disabled_by": None,
                    "entry_type": "service",
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "name_by_user": None,
                    "sw_version": "new_version",
                    "via_device_id": None,
                },
                {
                    "area_id": None,
                    "config_entries": [None],
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


async def test_removing_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Make sure we do not get duplicate entries."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id="456",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 2
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {"123", "456"}

    device_registry.async_clear_config_entry("123")
    entry = device_registry.async_get_device(identifiers={("bridgeid", "0123")})
    entry3_removed = device_registry.async_get_device(
        identifiers={("bridgeid", "4567")}
    )

    assert entry.config_entries == {"456"}
    assert entry3_removed is None

    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry2.id
    assert update_events[1]["changes"] == {"config_entries": {"123"}}
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry3.id
    assert "changes" not in update_events[2]
    assert update_events[3]["action"] == "update"
    assert update_events[3]["device_id"] == entry.id
    assert update_events[3]["changes"] == {"config_entries": {"456", "123"}}
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry3.id
    assert "changes" not in update_events[4]


async def test_deleted_device_removing_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Make sure we do not get duplicate entries."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id="456",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 2
    assert len(device_registry.deleted_devices) == 0
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {"123", "456"}

    device_registry.async_remove_device(entry.id)
    device_registry.async_remove_device(entry3.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    await hass.async_block_till_done()
    assert len(update_events) == 5
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry2.id
    assert update_events[1]["changes"] == {"config_entries": {"123"}}
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry3.id
    assert "changes" not in update_events[2]["device_id"]
    assert update_events[3]["action"] == "remove"
    assert update_events[3]["device_id"] == entry.id
    assert "changes" not in update_events[3]
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry3.id
    assert "changes" not in update_events[4]

    device_registry.async_clear_config_entry("123")
    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    device_registry.async_clear_config_entry("456")
    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 2

    # No event when a deleted device is purged
    await hass.async_block_till_done()
    assert len(update_events) == 5

    # Re-add, expect to keep the device id
    entry2 = device_registry.async_get_or_create(
        config_entry_id="456",
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
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry3.id != entry4.id


async def test_removing_area_id(device_registry: dr.DeviceRegistry) -> None:
    """Make sure we can clear area id."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
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


async def test_specifying_via_device_create(device_registry: dr.DeviceRegistry) -> None:
    """Test specifying a via_device and removal of the hub device."""
    via = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    light = device_registry.async_get_or_create(
        config_entry_id="456",
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


async def test_specifying_via_device_update(device_registry: dr.DeviceRegistry) -> None:
    """Test specifying a via_device and updating."""
    light = device_registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id is None

    via = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    light = device_registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id == via.id


async def test_loading_saving_data(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test that we load/save data correctly."""
    orig_via = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
        name="Original Name",
        sw_version="Orig SW 1",
        entry_type=None,
    )

    orig_light = device_registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
        disabled_by=dr.DeviceEntryDisabler.USER,
    )

    orig_light2 = device_registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "789")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    device_registry.async_remove_device(orig_light2.id)

    orig_light3 = device_registry.async_get_or_create(
        config_entry_id="789",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("hue", "abc")},
        manufacturer="manufacturer",
        model="light",
    )

    device_registry.async_get_or_create(
        config_entry_id="abc",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("abc", "123")},
        manufacturer="manufacturer",
        model="light",
    )

    device_registry.async_remove_device(orig_light3.id)

    orig_light4 = device_registry.async_get_or_create(
        config_entry_id="789",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("hue", "abc")},
        manufacturer="manufacturer",
        model="light",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    assert orig_light4.id == orig_light3.id

    orig_kitchen_light = device_registry.async_get_or_create(
        config_entry_id="999",
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
        orig_via.id, area_id="mock-area-id", name_by_user="mock-name-by-user"
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


async def test_no_unnecessary_changes(device_registry: dr.DeviceRegistry) -> None:
    """Make sure we do not consider devices changes."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("hue", "456"), ("bla", "123")},
    )
    with patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_schedule_save"
    ) as mock_save:
        entry2 = device_registry.async_get_or_create(
            config_entry_id="1234", identifiers={("hue", "456")}
        )

    assert entry.id == entry2.id
    assert len(mock_save.mock_calls) == 0


async def test_format_mac(device_registry: dr.DeviceRegistry) -> None:
    """Make sure we normalize mac addresses."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for mac in ["123456ABCDEF", "123456abcdef", "12:34:56:ab:cd:ef", "1234.56ab.cdef"]:
        test_entry = device_registry.async_get_or_create(
            config_entry_id="1234",
            connections={(dr.CONNECTION_NETWORK_MAC, mac)},
        )
        assert test_entry.id == entry.id, mac
        assert test_entry.connections == {
            (dr.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
        }

    # This should not raise
    for invalid in [
        "invalid_mac",
        "123456ABCDEFG",  # 1 extra char
        "12:34:56:ab:cdef",  # not enough :
        "12:34:56:ab:cd:e:f",  # too many :
        "1234.56abcdef",  # not enough .
        "123.456.abc.def",  # too many .
    ]:
        invalid_mac_entry = device_registry.async_get_or_create(
            config_entry_id="1234",
            connections={(dr.CONNECTION_NETWORK_MAC, invalid)},
        )
        assert list(invalid_mac_entry.connections)[0][1] == invalid


async def test_update(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Verify that we can update some attributes of a device."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "456"), ("bla", "123")},
    )
    new_identifiers = {("hue", "654"), ("bla", "321")}
    assert not entry.area_id
    assert not entry.name_by_user

    with patch.object(device_registry, "async_schedule_save") as mock_save:
        updated_entry = device_registry.async_update_device(
            entry.id,
            area_id="12345A",
            configuration_url="https://example.com/config",
            disabled_by=dr.DeviceEntryDisabler.USER,
            entry_type=dr.DeviceEntryType.SERVICE,
            hw_version="hw_version",
            manufacturer="Test Producer",
            model="Test Model",
            name_by_user="Test Friendly Name",
            name="name",
            new_identifiers=new_identifiers,
            suggested_area="suggested_area",
            sw_version="version",
            via_device_id="98765B",
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry == dr.DeviceEntry(
        area_id="12345A",
        config_entries={"1234"},
        configuration_url="https://example.com/config",
        connections={("mac", "12:34:56:ab:cd:ef")},
        disabled_by=dr.DeviceEntryDisabler.USER,
        entry_type=dr.DeviceEntryType.SERVICE,
        hw_version="hw_version",
        id=entry.id,
        identifiers={("bla", "321"), ("hue", "654")},
        manufacturer="Test Producer",
        model="Test Model",
        name_by_user="Test Friendly Name",
        name="name",
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
        == updated_entry
    )

    assert device_registry.async_get(updated_entry.id) is not None

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[1]["changes"] == {
        "area_id": None,
        "configuration_url": None,
        "disabled_by": None,
        "entry_type": None,
        "hw_version": None,
        "identifiers": {("bla", "123"), ("hue", "456")},
        "manufacturer": None,
        "model": None,
        "name": None,
        "name_by_user": None,
        "suggested_area": None,
        "sw_version": None,
        "via_device_id": None,
    }


async def test_update_remove_config_entries(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Make sure we do not get duplicate entries."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = device_registry.async_get_or_create(
        config_entry_id="456",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 2
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {"123", "456"}

    updated_entry = device_registry.async_update_device(
        entry2.id, remove_config_entry_id="123"
    )
    removed_entry = device_registry.async_update_device(
        entry3.id, remove_config_entry_id="123"
    )

    assert updated_entry.config_entries == {"456"}
    assert removed_entry is None

    removed_entry = device_registry.async_get_device(identifiers={("bridgeid", "4567")})

    assert removed_entry is None

    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry2.id
    assert update_events[1]["changes"] == {"config_entries": {"123"}}
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry3.id
    assert "changes" not in update_events[2]
    assert update_events[3]["action"] == "update"
    assert update_events[3]["device_id"] == entry.id
    assert update_events[3]["changes"] == {"config_entries": {"456", "123"}}
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry3.id
    assert "changes" not in update_events[4]


async def test_update_suggested_area(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    area_registry: ar.AreaRegistry,
    update_events,
) -> None:
    """Verify that we can update the suggested area version of a device."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
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
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[1]["changes"] == {"area_id": None, "suggested_area": None}

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
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test cleanup works."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)

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
        identifiers={("something", "d4")}, config_entry_id="non_existing"
    )

    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create("light", "hue", "e1", device_id=d1.id)
    ent_reg.async_get_or_create("light", "hue", "e2", device_id=d1.id)
    ent_reg.async_get_or_create("light", "hue", "e3", device_id=d3.id)

    dr.async_cleanup(hass, device_registry, ent_reg)

    assert device_registry.async_get_device(identifiers={("hue", "d1")}) is not None
    assert device_registry.async_get_device(identifiers={("hue", "d2")}) is not None
    assert device_registry.async_get_device(identifiers={("hue", "d3")}) is not None
    assert device_registry.async_get_device(identifiers={("something", "d4")}) is None


async def test_cleanup_device_registry_removes_expired_orphaned_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
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

    ent_reg = er.async_get(hass)
    dr.async_cleanup(hass, device_registry, ent_reg)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 3

    future_time = time.time() + dr.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        dr.async_cleanup(hass, device_registry, ent_reg)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 0


async def test_cleanup_startup(hass: HomeAssistant) -> None:
    """Test we run a cleanup on startup."""
    hass.state = CoreState.not_running

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
        "homeassistant.helpers.device_registry.Debouncer.async_call"
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
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Make sure device id is stable."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
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
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="123",
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
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["device_id"] == entry.id
    assert "changes" not in update_events[1]
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry2.id
    assert "changes" not in update_events[2]
    assert update_events[3]["action"] == "create"
    assert update_events[3]["device_id"] == entry3.id
    assert "changes" not in update_events[3]


async def test_restore_simple_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Make sure device id is stable."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_remove_device(entry.id)

    assert len(device_registry.devices) == 0
    assert len(device_registry.deleted_devices) == 1

    entry2 = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )
    entry3 = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    assert entry.id == entry3.id
    assert entry.id != entry2.id
    assert len(device_registry.devices) == 2
    assert len(device_registry.deleted_devices) == 0

    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["device_id"] == entry.id
    assert "changes" not in update_events[1]
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry2.id
    assert "changes" not in update_events[2]
    assert update_events[3]["action"] == "create"
    assert update_events[3]["device_id"] == entry3.id
    assert "changes" not in update_events[3]


async def test_restore_shared_device(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, update_events
) -> None:
    """Make sure device id is stable for shared devices."""
    entry = device_registry.async_get_or_create(
        config_entry_id="123",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(device_registry.devices) == 1
    assert len(device_registry.deleted_devices) == 0

    device_registry.async_get_or_create(
        config_entry_id="234",
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
        config_entry_id="123",
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
        config_entry_id="234",
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
        config_entry_id="123",
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
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert "changes" not in update_events[0]
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[1]["changes"] == {
        "config_entries": {"123"},
        "identifiers": {("entry_123", "0123")},
    }
    assert update_events[2]["action"] == "remove"
    assert update_events[2]["device_id"] == entry.id
    assert "changes" not in update_events[2]
    assert update_events[3]["action"] == "create"
    assert update_events[3]["device_id"] == entry.id
    assert "changes" not in update_events[3]
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry.id
    assert "changes" not in update_events[4]
    assert update_events[5]["action"] == "create"
    assert update_events[5]["device_id"] == entry.id
    assert "changes" not in update_events[5]
    assert update_events[6]["action"] == "update"
    assert update_events[6]["device_id"] == entry.id
    assert update_events[6]["changes"] == {
        "config_entries": {"234"},
        "identifiers": {("entry_234", "2345")},
    }


async def test_get_or_create_empty_then_set_default_values(
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test creating an entry, then setting default name, model, manufacturer."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert entry.name is None
    assert entry.model is None
    assert entry.manufacturer is None

    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"

    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
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
) -> None:
    """Test creating an entry, then setting name, model, manufacturer."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    assert entry.name is None
    assert entry.model is None
    assert entry.manufacturer is None

    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="name 1",
        model="model 1",
        manufacturer="manufacturer 1",
    )
    assert entry.name == "name 1"
    assert entry.model == "model 1"
    assert entry.manufacturer == "manufacturer 1"

    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
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
) -> None:
    """Test creating an entry, then setting default name, model, manufacturer."""
    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"

    entry = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        default_name="default name 2",
        default_model="default model 2",
        default_manufacturer="default manufacturer 2",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"


async def test_verify_suggested_area_does_not_overwrite_area_id(
    device_registry: dr.DeviceRegistry, area_registry: ar.AreaRegistry
) -> None:
    """Make sure suggested area does not override a set area id."""
    game_room_area = area_registry.async_create("Game Room")

    original_entry = device_registry.async_get_or_create(
        config_entry_id="1234",
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
        config_entry_id="1234",
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
    expectation,
) -> None:
    """Test configuration URL of device info is properly validated."""
    with expectation:
        device_registry.async_get_or_create(
            config_entry_id="1234",
            identifiers={("something", "1234")},
            name="name",
            configuration_url=configuration_url,
        )

    update_device = device_registry.async_get_or_create(
        config_entry_id="5678",
        identifiers={("something", "5678")},
        name="name",
    )
    with expectation:
        device_registry.async_update_device(
            update_device.id, configuration_url=configuration_url
        )


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_invalid_configuration_url_from_storage(
    hass: HomeAssistant, hass_storage: dict[str, Any]
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
                    "configuration_url": "invalid",
                    "connections": [],
                    "disabled_by": None,
                    "entry_type": dr.DeviceEntryType.SERVICE,
                    "hw_version": None,
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": None,
                    "model": None,
                    "name_by_user": None,
                    "name": None,
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
        config_entry_id="1234", identifiers={("serial", "12:34:56:AB:CD:EF")}
    )
    assert entry.configuration_url == "invalid"
