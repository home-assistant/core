"""Tests for the Device Registry."""
import asyncio
from unittest.mock import patch

import asynctest
import pytest

from homeassistant.core import callback
from homeassistant.helpers import device_registry

from tests.common import flush_store, mock_device_registry


@pytest.fixture
def registry(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def update_events(hass):
    """Capture update events."""
    events = []

    @callback
    def async_capture(event):
        events.append(event.data)

    hass.bus.async_listen(device_registry.EVENT_DEVICE_REGISTRY_UPDATED, async_capture)

    return events


async def test_get_or_create_returns_same_entry(hass, registry, update_events):
    """Make sure we do not duplicate entries."""
    entry = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        sw_version="sw-version",
        name="name",
        manufacturer="manufacturer",
        model="model",
    )
    entry2 = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "11:22:33:66:77:88")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
    )
    entry3 = registry.async_get_or_create(
        config_entry_id="1234",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
    )

    assert len(registry.devices) == 1
    assert entry.id == entry2.id
    assert entry.id == entry3.id
    assert entry.identifiers == {("bridgeid", "0123")}

    assert entry3.manufacturer == "manufacturer"
    assert entry3.model == "model"
    assert entry3.name == "name"
    assert entry3.sw_version == "sw-version"

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
                    "area_id": "12345A",
                    "name_by_user": "Test Friendly Name",
                }
            ]
        },
    }

    registry = await device_registry.async_get_registry(hass)

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
    assert isinstance(entry.config_entries, set)


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
    entry = registry.async_get_device({("bridgeid", "0123")}, set())
    entry3_removed = registry.async_get_device({("bridgeid", "4567")}, set())

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
    entry_wo_area = registry.async_get_device({("bridgeid", "0123")}, set())

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


async def test_loading_saving_data(hass, registry):
    """Test that we load/save data correctly."""
    orig_via = registry.async_get_or_create(
        config_entry_id="123",
        connections={(device_registry.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        identifiers={("hue", "0123")},
        manufacturer="manufacturer",
        model="via",
    )

    orig_light = registry.async_get_or_create(
        config_entry_id="456",
        connections=set(),
        identifiers={("hue", "456")},
        manufacturer="manufacturer",
        model="light",
        via_device=("hue", "0123"),
    )

    assert len(registry.devices) == 2

    # Now load written data in new registry
    registry2 = device_registry.DeviceRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    # Ensure same order
    assert list(registry.devices) == list(registry2.devices)

    new_via = registry2.async_get_device({("hue", "0123")}, set())
    new_light = registry2.async_get_device({("hue", "456")}, set())

    assert orig_via == new_via
    assert orig_light == new_light


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
        )

    assert mock_save.call_count == 1
    assert updated_entry != entry
    assert updated_entry.area_id == "12345A"
    assert updated_entry.manufacturer == "Test Producer"
    assert updated_entry.model == "Test Model"
    assert updated_entry.name_by_user == "Test Friendly Name"
    assert updated_entry.identifiers == new_identifiers
    assert updated_entry.via_device_id == "98765B"


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

    removed_entry = registry.async_get_device({("bridgeid", "4567")}, set())

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


async def test_loading_race_condition(hass):
    """Test only one storage load called when concurrent loading occurred ."""
    with asynctest.patch(
        "homeassistant.helpers.device_registry.DeviceRegistry.async_load"
    ) as mock_load:
        results = await asyncio.gather(
            device_registry.async_get_registry(hass),
            device_registry.async_get_registry(hass),
        )

        mock_load.assert_called_once_with()
        assert results[0] == results[1]


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
