"""Tests for the Device Registry."""
import time
from unittest.mock import patch

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, callback
from homeassistant.helpers import device_registry, entity_registry

from tests.common import (
    MockConfigEntry,
    flush_store,
    mock_area_registry,
    mock_device_registry,
)


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def area_registry(hass):
    """Return an empty, loaded, registry."""
    return mock_area_registry(hass)


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(device_registry.EVENT_DEVICE_REGISTRY_UPDATED, async_capture)

    return events


async def test_get_or_create_returns_same_entry(
    hass, registry, area_registry, update_events
):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "11:22:33:66:77:88")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
        suggested_area="Game Room",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    game_room_area = area_registry.async_get_area_by_name("Game Room")
    assert game_room_area is not None
    assert len(area_registry.areas) == 1

    assert len(registry.devices) == 1
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
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id


async def test_requirement_for_identifier_or_connection(registry):
    """Make sure we do require some descriptor of device."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers=set(),
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="1234",
        connections=set(),
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="1234",
        connections=set(),
        identifiers=set(),
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 2
    assert entry
    assert entry2
    assert entry3 is None


async def test_multiple_config_entries(registry):
    """Make sure we do not get duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="456",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 1
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry2.config_entries == {"123", "456"}


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_from_storage(hass, hass_storage):
    """Test loading stored devices on start."""
    hass_storage[device_registry.STORAGE_KEY] = {
        "version": device_registry.STORAGE_VERSION,
        "data": {
            "devices": [
                {
                    "config_entries": ["1234"],
                    "connections": [["Zigbee", "01.23.45.67.89"]],
                    "id": "abcdefghijklm",
                    "identifiers": [["serial", "12:34:56:AB:CD:EF"]],
                    "manufacturer": "manufacturer",
                    "model": "model",
                    "name": "name",
                    "sw_version": "version",
                    "entry_type": "service",
                    "area_id": "12345A",
                    "name_by_user": "Test Friendly Name",
                    "disabled_by": "user",
                    "suggested_area": "Kitchen",
                }
            ],
            "deleted_devices": [
                {
                    "config_entries": ["1234"],
                    "connections": [["Zigbee", "23.45.67.89.01"]],
                    "id": "bcdefghijklmn",
                    "identifiers": [["serial", "34:56:AB:CD:EF:12"]],
                }
            ],
        },
    }

    await device_registry.async_load(hass)
    registry = device_registry.async_get(hass)
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 1

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("Zigbee", "01.23.45.67.89")},
        identifiers={("serial", "12:34:56:AB:CD:EF")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.id == "abcdefghijklm"
    assert entry.area_id == "12345A"
    assert entry.name_by_user == "Test Friendly Name"
    assert entry.entry_type == "service"
    assert entry.disabled_by == "user"
    assert isinstance(entry.config_entries, set)
    assert isinstance(entry.connections, set)
    assert isinstance(entry.identifiers, set)

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("Zigbee", "23.45.67.89.01")},
        identifiers={("serial", "34:56:AB:CD:EF:12")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.id == "bcdefghijklmn"
    assert isinstance(entry.config_entries, set)
    assert isinstance(entry.connections, set)
    assert isinstance(entry.identifiers, set)


async def test_removing_config_entries(hass, registry, update_events):
    """Make sure we do not get duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="456",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 2
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {"123", "456"}

    registry.async_clear_config_entry("123")
    entry = registry.async_get_device({("bridgeid", "0123")})
    entry3_removed = registry.async_get_device({("bridgeid", "4567")})

    assert entry.config_entries == {"456"}
    assert entry3_removed is None

    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry2.id
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry3.id
    assert update_events[3]["action"] == "update"
    assert update_events[3]["device_id"] == entry.id
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry3.id


async def test_deleted_device_removing_config_entries(hass, registry, update_events):
    """Make sure we do not get duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="456",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 2
    assert len(registry.deleted_devices) == 0
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {"123", "456"}

    registry.async_remove_device(entry.id)
    registry.async_remove_device(entry3.id)

    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 2

    await hass.async_block_till_done()
    assert len(update_events) == 5
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry2.id
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry3.id
    assert update_events[3]["action"] == "remove"
    assert update_events[3]["device_id"] == entry.id
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry3.id

    registry.async_clear_config_entry("123")
    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 2

    registry.async_clear_config_entry("456")
    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 2

    # No event when a deleted device is purged
    await hass.async_block_till_done()
    assert len(update_events) == 5

    # Re-add, expect to keep the device id
    entry2 = registry.async_get_or_create(
        config_entry_id="456",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry2.id

    future_time = time.time() + device_registry.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        registry.async_purge_expired_orphaned_devices()

    # Re-add, expect to get a new device id after the purge
    entry4 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry3.id != entry4.id


async def test_removing_area_id(registry):
    """Make sure we can clear area id."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    entry_w_area = registry.async_update_device(entry.id, area_id="12345A")

    registry.async_clear_area_id("12345A")
    entry_wo_area = registry.async_get_device({("bridgeid", "0123")})

    assert not entry_wo_area.area_id
    assert entry_w_area != entry_wo_area


async def test_deleted_device_removing_area_id(registry):
    """Make sure we can clear area id of deleted device."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    entry_w_area = registry.async_update_device(entry.id, area_id="12345A")

    registry.async_remove_device(entry.id)
    registry.async_clear_area_id("12345A")

    entry2 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    assert entry.id == entry2.id

    entry_wo_area = registry.async_get_device({("bridgeid", "0123")})

    assert not entry_wo_area.area_id
    assert entry_w_area != entry_wo_area


async def test_specifying_via_device_create(registry):
    """Test specifying a via_device and updating."""
    via = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    light = registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id == via.id


async def test_specifying_via_device_update(registry):
    """Test specifying a via_device and updating."""
    light = registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id is None

    via = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    light = registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert light.via_device_id == via.id


async def test_loading_saving_data(hass, registry, area_registry):
    """Test that we load/save data correctly."""
    orig_via = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
        name="Original Name",
        sw_version="Orig SW 1",
        entry_type="device",
    )

    orig_light = registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
        disabled_by="user",
    )

    orig_light2 = registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "789")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    registry.async_remove_device(orig_light2.id)

    orig_light3 = registry.async_get_or_create(
        config_entry_id="789",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("hue", "abc")},
        manufacturer="manufacturer",
        model="light",
    )

    registry.async_get_or_create(
        config_entry_id="abc",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("abc", "123")},
        manufacturer="manufacturer",
        model="light",
    )

    registry.async_remove_device(orig_light3.id)

    orig_light4 = registry.async_get_or_create(
        config_entry_id="789",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:AB:CD:EF:12")},
        identifiers={("hue", "abc")},
        manufacturer="manufacturer",
        model="light",
    )

    assert orig_light4.id == orig_light3.id

    orig_kitchen_light = registry.async_get_or_create(
        config_entry_id="999",
        connections=set(),
        identifiers={("hue", "999")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
        disabled_by="user",
        suggested_area="Kitchen",
    )

    assert len(registry.devices) == 4
    assert len(registry.deleted_devices) == 1

    orig_via = registry.async_update_device(
        orig_via.id, area_id="mock-area-id", name_by_user="mock-name-by-user"
    )

    # Now load written data in new registry
    registry2 = device_registry.DeviceRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    # Ensure same order
    assert list(registry.devices) == list(registry2.devices)
    assert list(registry.deleted_devices) == list(registry2.deleted_devices)

    new_via = registry2.async_get_device({("hue", "0123")})
    new_light = registry2.async_get_device({("hue", "456")})
    new_light4 = registry2.async_get_device({("hue", "abc")})

    assert orig_via == new_via
    assert orig_light == new_light
    assert orig_light4 == new_light4

    # Ensure a save/load cycle does not keep suggested area
    new_kitchen_light = registry2.async_get_device({("hue", "999")})
    assert orig_kitchen_light.suggested_area == "Kitchen"

    orig_kitchen_light_witout_suggested_area = registry.async_update_device(
        orig_kitchen_light.id, suggested_area=None
    )
    orig_kitchen_light_witout_suggested_area.suggested_area is None
    assert orig_kitchen_light_witout_suggested_area == new_kitchen_light


async def test_no_unnecessary_changes(registry):
    """Make sure we do not consider devices changes."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("hue", "456"), ("bla", "123")},
    )
    with patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_schedule_save"
    ) as mock_save:
        entry2 = registry.async_get_or_create(
            config_entry_id="1234", identifiers={("hue", "456")}
        )

    assert entry.id == entry2.id
    assert len(mock_save.mock_calls) == 0


async def test_format_mac(registry):
    """Make sure we normalize mac addresses."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )
    for mac in ["123456ABCDEF", "123456abcdef", "12:34:56:ab:cd:ef", "1234.56ab.cdef"]:
        test_entry = registry.async_get_or_create(
            config_entry_id="1234",
            connections={(device_registry.CONNECTION_NETWORK_MAC, mac)},
        )
        assert test_entry.id == entry.id, mac
        assert test_entry.connections == {
            (device_registry.CONNECTION_NETWORK_MAC, "12:34:56:ab:cd:ef")
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
        invalid_mac_entry = registry.async_get_or_create(
            config_entry_id="1234",
            connections={(device_registry.CONNECTION_NETWORK_MAC, invalid)},
        )
        assert list(invalid_mac_entry.connections)[0][1] == invalid


async def test_update(registry):
    """Verify that we can update some attributes of a device."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "456"), ("bla", "123")},
    )
    new_identifiers = {("hue", "654"), ("bla", "321")}
    assert not entry.area_id
    assert not entry.name_by_user

    with patch.object(registry, "async_schedule_save") as mock_save:
        updated_entry = registry.async_update_device(
            entry.id,
            area_id="12345A",
            manufacturer="Test Producer",
            model="Test Model",
            name_by_user="Test Friendly Name",
            new_identifiers=new_identifiers,
            via_device_id="98765B",
            disabled_by="user",
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry.area_id == "12345A"
    assert updated_entry.manufacturer == "Test Producer"
    assert updated_entry.model == "Test Model"
    assert updated_entry.name_by_user == "Test Friendly Name"
    assert updated_entry.identifiers == new_identifiers
    assert updated_entry.via_device_id == "98765B"
    assert updated_entry.disabled_by == "user"

    assert registry.async_get_device({("hue", "456")}) is None
    assert registry.async_get_device({("bla", "123")}) is None

    assert registry.async_get_device({("hue", "654")}) == updated_entry
    assert registry.async_get_device({("bla", "321")}) == updated_entry

    assert (
        registry.async_get_device(
            {}, {(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")}
        )
        == updated_entry
    )

    assert registry.async_get(updated_entry.id) is not None


async def test_update_remove_config_entries(hass, registry, update_events):
    """Make sure we do not get duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="456",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 2
    assert entry.id == entry2.id
    assert entry.id != entry3.id
    assert entry2.config_entries == {"123", "456"}

    updated_entry = registry.async_update_device(
        entry2.id, remove_config_entry_id="123"
    )
    removed_entry = registry.async_update_device(
        entry3.id, remove_config_entry_id="123"
    )

    assert updated_entry.config_entries == {"456"}
    assert removed_entry is None

    removed_entry = registry.async_get_device({("bridgeid", "4567")})

    assert removed_entry is None

    await hass.async_block_till_done()

    assert len(update_events) == 5
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry2.id
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry3.id
    assert update_events[3]["action"] == "update"
    assert update_events[3]["device_id"] == entry.id
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry3.id


async def test_update_sw_version(registry):
    """Verify that we can update software version of a device."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bla", "123")},
    )
    assert not entry.sw_version
    sw_version = "0x20020263"

    with patch.object(registry, "async_schedule_save") as mock_save:
        updated_entry = registry.async_update_device(entry.id, sw_version=sw_version)

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry.sw_version == sw_version


async def test_update_suggested_area(registry, area_registry):
    """Verify that we can update the suggested area version of a device."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bla", "123")},
    )
    assert not entry.suggested_area
    assert entry.area_id is None

    suggested_area = "Pool"

    with patch.object(registry, "async_schedule_save") as mock_save:
        updated_entry = registry.async_update_device(
            entry.id, suggested_area=suggested_area
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry.suggested_area == suggested_area

    pool_area = area_registry.async_get_area_by_name("Pool")
    assert pool_area is not None
    assert updated_entry.area_id == pool_area.id
    assert len(area_registry.areas) == 1


async def test_cleanup_device_registry(hass, registry):
    """Test cleanup works."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)

    d1 = registry.async_get_or_create(
        identifiers={("hue", "d1")}, config_entry_id=config_entry.entry_id
    )
    registry.async_get_or_create(
        identifiers={("hue", "d2")}, config_entry_id=config_entry.entry_id
    )
    d3 = registry.async_get_or_create(
        identifiers={("hue", "d3")}, config_entry_id=config_entry.entry_id
    )
    registry.async_get_or_create(
        identifiers={("something", "d4")}, config_entry_id="non_existing"
    )

    ent_reg = await entity_registry.async_get_registry(hass)
    ent_reg.async_get_or_create("light", "hue", "e1", device_id=d1.id)
    ent_reg.async_get_or_create("light", "hue", "e2", device_id=d1.id)
    ent_reg.async_get_or_create("light", "hue", "e3", device_id=d3.id)

    device_registry.async_cleanup(hass, registry, ent_reg)

    assert registry.async_get_device({("hue", "d1")}) is not None
    assert registry.async_get_device({("hue", "d2")}) is not None
    assert registry.async_get_device({("hue", "d3")}) is not None
    assert registry.async_get_device({("something", "d4")}) is None


async def test_cleanup_device_registry_removes_expired_orphaned_devices(hass, registry):
    """Test cleanup removes expired orphaned devices."""
    config_entry = MockConfigEntry(domain="hue")
    config_entry.add_to_hass(hass)

    registry.async_get_or_create(
        identifiers={("hue", "d1")}, config_entry_id=config_entry.entry_id
    )
    registry.async_get_or_create(
        identifiers={("hue", "d2")}, config_entry_id=config_entry.entry_id
    )
    registry.async_get_or_create(
        identifiers={("hue", "d3")}, config_entry_id=config_entry.entry_id
    )

    registry.async_clear_config_entry(config_entry.entry_id)
    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 3

    ent_reg = await entity_registry.async_get_registry(hass)
    device_registry.async_cleanup(hass, registry, ent_reg)

    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 3

    future_time = time.time() + device_registry.ORPHANED_DEVICE_KEEP_SECONDS + 1

    with patch("time.time", return_value=future_time):
        device_registry.async_cleanup(hass, registry, ent_reg)

    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 0


async def test_cleanup_startup(hass):
    """Test we run a cleanup on startup."""
    hass.state = CoreState.not_running
    await device_registry.async_get_registry(hass)

    with patch(
        "homeassistant.helpers.device_registry.Debouncer.async_call"
    ) as mock_call:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await hass.async_block_till_done()

    assert len(mock_call.mock_calls) == 1


@pytest.mark.parametrize("load_registries", [False])
async def test_cleanup_entity_registry_change(hass):
    """Test we run a cleanup when entity registry changes.

    Don't pre-load the registries as the debouncer will then not be waiting for
    EVENT_ENTITY_REGISTRY_UPDATED events.
    """
    await device_registry.async_load(hass)
    await entity_registry.async_load(hass)
    ent_reg = entity_registry.async_get(hass)

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


async def test_restore_device(hass, registry, update_events):
    """Make sure device id is stable."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    registry.async_remove_device(entry.id)

    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 1

    entry2 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry3.id
    assert entry.id != entry2.id
    assert len(registry.devices) == 2
    assert len(registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry2.id
    assert update_events[3]["action"] == "create"
    assert update_events[3]["device_id"] == entry3.id


async def test_restore_simple_device(hass, registry, update_events):
    """Make sure device id is stable."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    registry.async_remove_device(entry.id)

    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 1

    entry2 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "34:56:78:CD:EF:12")},
        identifiers={("bridgeid", "4567")},
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
    )

    assert entry.id == entry3.id
    assert entry.id != entry2.id
    assert len(registry.devices) == 2
    assert len(registry.deleted_devices) == 0

    await hass.async_block_till_done()

    assert len(update_events) == 4
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert update_events[1]["action"] == "remove"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[2]["action"] == "create"
    assert update_events[2]["device_id"] == entry2.id
    assert update_events[3]["action"] == "create"
    assert update_events[3]["device_id"] == entry3.id


async def test_restore_shared_device(hass, registry, update_events):
    """Make sure device id is stable for shared devices."""
    entry = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    registry.async_get_or_create(
        config_entry_id="234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_234", "2345")},
        manufacturer="manufacturer",
        model="model",
    )

    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    registry.async_remove_device(entry.id)

    assert len(registry.devices) == 0
    assert len(registry.deleted_devices) == 1

    entry2 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry2.id
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    assert isinstance(entry2.config_entries, set)
    assert isinstance(entry2.connections, set)
    assert isinstance(entry2.identifiers, set)

    registry.async_remove_device(entry.id)

    entry3 = registry.async_get_or_create(
        config_entry_id="234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_234", "2345")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry3.id
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    assert isinstance(entry3.config_entries, set)
    assert isinstance(entry3.connections, set)
    assert isinstance(entry3.identifiers, set)

    entry4 = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("entry_123", "0123")},
        manufacturer="manufacturer",
        model="model",
    )

    assert entry.id == entry4.id
    assert len(registry.devices) == 1
    assert len(registry.deleted_devices) == 0

    assert isinstance(entry4.config_entries, set)
    assert isinstance(entry4.connections, set)
    assert isinstance(entry4.identifiers, set)

    await hass.async_block_till_done()

    assert len(update_events) == 7
    assert update_events[0]["action"] == "create"
    assert update_events[0]["device_id"] == entry.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id
    assert update_events[2]["action"] == "remove"
    assert update_events[2]["device_id"] == entry.id
    assert update_events[3]["action"] == "create"
    assert update_events[3]["device_id"] == entry.id
    assert update_events[4]["action"] == "remove"
    assert update_events[4]["device_id"] == entry.id
    assert update_events[5]["action"] == "create"
    assert update_events[5]["device_id"] == entry.id
    assert update_events[1]["action"] == "update"
    assert update_events[1]["device_id"] == entry.id


async def test_get_or_create_empty_then_set_default_values(hass, registry):
    """Test creating an entry, then setting default name, model, manufacturer."""
    entry = registry.async_get_or_create(
        identifiers={("bridgeid", "0123")}, config_entry_id="1234"
    )
    assert entry.name is None
    assert entry.model is None
    assert entry.manufacturer is None

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "0123")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "0123")},
        default_name="default name 2",
        default_model="default model 2",
        default_manufacturer="default manufacturer 2",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"


async def test_get_or_create_empty_then_update(hass, registry):
    """Test creating an entry, then setting name, model, manufacturer."""
    entry = registry.async_get_or_create(
        identifiers={("bridgeid", "0123")}, config_entry_id="1234"
    )
    assert entry.name is None
    assert entry.model is None
    assert entry.manufacturer is None

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "0123")},
        name="name 1",
        model="model 1",
        manufacturer="manufacturer 1",
    )
    assert entry.name == "name 1"
    assert entry.model == "model 1"
    assert entry.manufacturer == "manufacturer 1"

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "0123")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "name 1"
    assert entry.model == "model 1"
    assert entry.manufacturer == "manufacturer 1"


async def test_get_or_create_sets_default_values(hass, registry):
    """Test creating an entry, then setting default name, model, manufacturer."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "0123")},
        default_name="default name 1",
        default_model="default model 1",
        default_manufacturer="default manufacturer 1",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"

    entry = registry.async_get_or_create(
        config_entry_id="1234",
        identifiers={("bridgeid", "0123")},
        default_name="default name 2",
        default_model="default model 2",
        default_manufacturer="default manufacturer 2",
    )
    assert entry.name == "default name 1"
    assert entry.model == "default model 1"
    assert entry.manufacturer == "default manufacturer 1"


async def test_verify_suggested_area_does_not_overwrite_area_id(
    hass, registry, area_registry
):
    """Make sure suggested area does not override a set area id."""
    game_room_area = area_registry.async_create("Game Room")

    original_entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
    )
    entry = registry.async_update_device(original_entry.id, area_id=game_room_area.id)

    assert entry.area_id == game_room_area.id

    entry2 = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
        suggested_area="New Game Room",
    )
    assert entry2.area_id == game_room_area.id
