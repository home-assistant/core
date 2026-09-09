"""The tests for the Rfxtrx component."""

from unittest.mock import ANY, Mock, call, patch

import RFXtrx as rfxtrxmod

from homeassistant.components.rfxtrx import (
    DOMAIN,
    DeviceTuple,
    get_device_tuple_from_device,
    get_pt2262_cmd,
    get_pt2262_deviceid,
    get_rfx_object,
)
from homeassistant.components.rfxtrx.const import (
    EVENT_RFXTRX_EVENT,
    SUBENTRY_TYPE_DEVICE,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentryDataWithId
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import ENTRY_VERSION
from .conftest import get_device_identifier, setup_rfx_test_cfg

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

SOME_PROTOCOLS = ["ac", "arc"]


async def test_fire_event(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, rfxtrx
) -> None:
    """Test fire event."""
    mock_entry = await setup_rfx_test_cfg(
        hass,
        device="/dev/serial/by-id/usb-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
        automatic_add=True,
        devices={
            "0b1100cd0213c7f210010f51": {},
            "0716000100900970": {},
        },
    )

    calls = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        assert event.event_type == "rfxtrx_event"
        calls.append(event.data)

    hass.bus.async_listen(EVENT_RFXTRX_EVENT, record_event)

    await rfxtrx.signal("0b1100cd0213c7f210010f51")
    await rfxtrx.signal("0716000100900970")

    device_id_1 = device_registry.async_get_device_by_identifier(
        get_device_identifier(mock_entry, "11_0_213c7f2:16"), mock_entry.entry_id
    )
    assert device_id_1

    device_id_2 = device_registry.async_get_device_by_identifier(
        get_device_identifier(mock_entry, "16_0_00:90"), mock_entry.entry_id
    )
    assert device_id_2

    assert calls == [
        {
            "packet_type": 17,
            "sub_type": 0,
            "type_string": "AC",
            "id_string": "213c7f2:16",
            "data": "0b1100cd0213c7f210010f51",
            "values": {"Command": "On", "Rssi numeric": 5},
            "device_id": device_id_1.id,
        },
        {
            "packet_type": 22,
            "sub_type": 0,
            "type_string": "Byron SX",
            "id_string": "00:90",
            "data": "0716000100900970",
            "values": {"Command": "Sound 9", "Rssi numeric": 7, "Sound": 9},
            "device_id": device_id_2.id,
        },
    ]


async def test_send(hass: HomeAssistant, rfxtrx) -> None:
    """Test configuration."""
    await setup_rfx_test_cfg(hass, device="/dev/null", devices={})

    await hass.services.async_call(
        DOMAIN, "send", {"event": "0a520802060101ff0f0269"}, blocking=True
    )

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0a\x52\x08\x02\x06\x01\x01\xff\x0f\x02\x69"))
    ]


def test_get_rfx_object_invalid_hex() -> None:
    """Test that an invalid hex packet id returns None."""
    assert get_rfx_object("not_hex") is None


def test_get_pt2262_deviceid_no_data_bits() -> None:
    """Test that no data bits returns None."""
    assert get_pt2262_deviceid("aabbcc", None) is None


def test_get_pt2262_deviceid_invalid_hex() -> None:
    """Test that an invalid hex device id returns None."""
    assert get_pt2262_deviceid("not_hex", 4) is None


def test_get_pt2262_cmd_invalid_hex() -> None:
    """Test that an invalid hex device id returns None."""
    assert get_pt2262_cmd("not_hex", 4) is None


async def test_ws_device_remove(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test removing a device through device registry."""
    assert await async_setup_component(hass, "config", {})

    device_tuple = DeviceTuple("11", "0", "213c7f2:16")
    mock_entry = await setup_rfx_test_cfg(
        hass,
        devices={
            "0b1100cd0213c7f210010f51": {"fire_event": True, "device_id": device_tuple},
        },
    )

    identifier = get_device_identifier(mock_entry, device_tuple.unique_id)
    device_entry = device_registry.async_get_device_by_identifier(
        identifier, mock_entry.entry_id
    )
    assert device_entry

    # Ask to remove existing device
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id)
    assert response["success"]

    # Verify device entry is removed
    assert (
        device_registry.async_get_device_by_identifier(identifier, mock_entry.entry_id)
        is None
    )

    # Verify that the config entry has removed the device
    assert mock_entry.subentries == {}


async def test_connect(
    rfxtrx, connect_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test that we attempt to connect to the device."""

    config_entry = await setup_rfx_test_cfg(hass, device="/dev/ttyUSBfake")
    transport_mock.assert_called_once_with("/dev/ttyUSBfake")
    connect_mock.assert_called_once_with(transport_mock.return_value, ANY, modes=ANY)
    rfxtrx.connect.assert_called_once_with(ANY)

    assert config_entry.state is ConfigEntryState.LOADED


async def test_connect_network(
    rfxtrx, connect_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test that we attempt to connect to the device."""

    config_entry = await setup_rfx_test_cfg(hass, host="localhost", port=1234)
    transport_mock.assert_called_once_with(("localhost", 1234))
    connect_mock.assert_called_once_with(transport_mock.return_value, ANY, modes=ANY)
    rfxtrx.connect.assert_called_once_with(ANY)

    assert config_entry.state is ConfigEntryState.LOADED


async def test_connect_with_protocols(
    rfxtrx, connect_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test that we attempt to set protocols."""
    config_entry = await setup_rfx_test_cfg(
        hass, device="/dev/ttyUSBfake", protocols=SOME_PROTOCOLS
    )
    transport_mock.assert_called_once_with("/dev/ttyUSBfake")
    connect_mock.assert_called_once_with(
        transport_mock.return_value, ANY, modes=SOME_PROTOCOLS
    )
    rfxtrx.connect.assert_called_once_with(ANY)

    assert config_entry.state is ConfigEntryState.LOADED


async def test_connect_timeout(
    rfxtrx, connect_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test that we attempt to connect to the device."""

    rfxtrx.connect.side_effect = TimeoutError

    config_entry = await setup_rfx_test_cfg(hass, device="/dev/ttyUSBfake")
    transport_mock.assert_called_once_with("/dev/ttyUSBfake")
    connect_mock.assert_called_once_with(transport_mock.return_value, ANY, modes=ANY)
    rfxtrx.connect.assert_called_once_with(ANY)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_connect_failed(
    rfxtrx, connect_mock, transport_mock, hass: HomeAssistant
) -> None:
    """Test that we attempt to connect to the device."""

    rfxtrx.connect.side_effect = rfxtrxmod.RFXtrxTransportError

    config_entry = await setup_rfx_test_cfg(hass, device="/dev/ttyUSBfake")
    transport_mock.assert_called_once_with("/dev/ttyUSBfake")
    connect_mock.assert_called_once_with(transport_mock.return_value, ANY, modes=ANY)
    rfxtrx.connect.assert_called_once_with(ANY)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_reconnect(rfxtrx, hass: HomeAssistant) -> None:
    """Test that we reconnect on connection loss."""
    config_entry = await setup_rfx_test_cfg(hass, device="/dev/ttyUSBfake")

    assert config_entry.state is ConfigEntryState.LOADED
    rfxtrx.connect.call_count = 1

    await hass.async_add_executor_job(
        rfxtrx.event_callback,
        rfxtrxmod.ConnectionLost(),
    )
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    rfxtrx.connect.call_count = 2


async def test_shutdown_closes_connection(rfxtrx, hass: HomeAssistant) -> None:
    """Test the connection is closed when Home Assistant stops."""
    await setup_rfx_test_cfg(hass, device="/dev/ttyUSBfake")

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    rfxtrx.close_connection.assert_called_once()


async def test_unload_entry_platforms_fail(rfxtrx, hass: HomeAssistant) -> None:
    """Test unload fails if a platform fails to unload."""
    config_entry = await setup_rfx_test_cfg(hass, device="/dev/ttyUSBfake")

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(config_entry.entry_id)

    assert result is False


async def test_receive_event_without_device(rfxtrx, hass: HomeAssistant) -> None:
    """Test an event without a device is ignored."""
    await setup_rfx_test_cfg(hass, devices={})

    mock_event = Mock(spec=rfxtrxmod.RFXtrxEvent)
    mock_event.device = None
    await hass.async_add_executor_job(rfxtrx.event_callback, mock_event)
    await hass.async_block_till_done()


async def test_ignores_non_device_subentries(hass: HomeAssistant) -> None:
    """Test that a subentry of a different type is ignored."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "device": "abcd",
            "host": None,
            "port": None,
            "automatic_add": False,
            "protocols": None,
        },
        subentries_data=(
            {
                "data": {},
                "subentry_type": "other",
                "title": "Not a device",
                "unique_id": None,
            },
        ),
        unique_id=DOMAIN,
        version=ENTRY_VERSION,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_updated_device_other_entry_ignored(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test removing a device from another config entry is ignored."""
    entry = await setup_rfx_test_cfg(hass, devices={"0b1100cd0213c7f230010f71": {}})
    subentry = next(iter(entry.subentries.values()))

    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={("other", "id")},
    )

    device_registry.async_remove_device(other_device.id)
    await hass.async_block_till_done()

    # Our own subentry is unaffected.
    assert entry.subentries == {subentry.subentry_id: subentry}


async def test_updated_device_no_identifier_ignored(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test removing a device without a rfxtrx identifier is ignored."""
    entry = await setup_rfx_test_cfg(hass, devices={"0b1100cd0213c7f230010f71": {}})
    subentry = next(iter(entry.subentries.values()))

    stray_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other", "id")},
    )

    device_registry.async_remove_device(stray_device.id)
    await hass.async_block_till_done()

    # Our own subentry is unaffected.
    assert entry.subentries == {subentry.subentry_id: subentry}


async def test_migrate_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test successful migration of entry data."""
    legacy_config = {
        "device": "abcd",
        "host": None,
        "port": None,
        "automatic_add": True,
        "protocols": [],
        "devices": {
            "0b1100cd0213c7f210010f51": {
                "fire_event": True,
                "device_id": ["11", "0", "213c7f2:16"],
            },
            "0716000100900970": {},
            "not_hex": {},
            # Two legacy event codes that mask to the same PT2262 device.
            "0913000022670e013970": {"data_bits": 4, "off_delay": 5},
            "09130000226707013970": {"data_bits": 4, "off_delay": 99},
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DOMAIN, data=legacy_config, version=1
    )
    entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, "11", "0", "213c7f2:16"),
            ("dummy", "id"),
        },
    )
    # Already in the new string format, e.g. from a previously interrupted
    # migration attempt.
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "16_0_00:90")},
    )
    # A device with no rfxtrx identifier at all - untouched by migration.
    device_3 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("dummy_only", "id")},
    )
    # A device with a string format identifier that matches no subentry.
    device_5 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "99_9_ffffff")},
    )

    entity_1 = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "11_0_213c7f2:16_signal_strength",
        config_entry=entry,
        device_id=device_1.id,
    )
    entity_2 = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        "16_0_00:90",
        config_entry=entry,
        device_id=device_2.id,
    )
    entity_3 = entity_registry.async_get_or_create(
        "event",
        DOMAIN,
        "11_0_213c7f2:16",
        config_entry=entry,
        device_id=device_1.id,
        translation_key="command",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert dict(entry.data) == {
        "device": "abcd",
        "host": None,
        "port": None,
        "automatic_add": True,
        "protocols": [],
    }
    assert entry.version == 3

    subentries = {
        subentry.unique_id: subentry for subentry in entry.subentries.values()
    }
    duplicate_event = get_rfx_object("0913000022670e013970")
    assert duplicate_event
    duplicate_device_id = get_device_tuple_from_device(
        duplicate_event.device, data_bits=4
    )
    assert subentries.keys() == {
        "11_0_213c7f2:16",
        "16_0_00:90",
        duplicate_device_id.unique_id,
    }

    # Only one subentry is created for the two event codes that mask to the
    # same device, using the data from whichever is processed first.
    subentry_dup = subentries[duplicate_device_id.unique_id]
    assert subentry_dup.data["event_code"] == "0913000022670e013970"
    assert subentry_dup.data["off_delay"] == 5

    subentry_1 = subentries["11_0_213c7f2:16"]
    assert subentry_1.title == "AC 213c7f2:16"
    assert dict(subentry_1.data) == {
        "fire_event": True,
        "event_code": "0b1100cd0213c7f210010f51",
    }

    subentry_2 = subentries["16_0_00:90"]
    assert subentry_2.title == "Byron SX 00:90"
    assert dict(subentry_2.data) == {"event_code": "0716000100900970"}

    device_1 = device_registry.async_get(device_1.id)
    assert device_1
    assert device_1.identifiers == {
        (DOMAIN, subentry_1.subentry_id),
        ("dummy", "id"),
    }
    assert device_1.config_subentry_id == subentry_1.subentry_id

    device_2 = device_registry.async_get(device_2.id)
    assert device_2
    assert device_2.identifiers == {
        (DOMAIN, subentry_2.subentry_id),
    }
    assert device_2.config_subentry_id == subentry_2.subentry_id

    # Device with no rfxtrx identifier is left untouched.
    device_3 = device_registry.async_get(device_3.id)
    assert device_3
    assert device_3.identifiers == {("dummy_only", "id")}
    assert device_3.config_subentry_id is None

    # Device whose identifier matches no subentry is left untouched.
    device_5 = device_registry.async_get(device_5.id)
    assert device_5
    assert device_5.identifiers == {(DOMAIN, "99_9_ffffff")}
    assert device_5.config_subentry_id is None

    entity_1 = entity_registry.async_get(entity_1.entity_id)
    assert entity_1
    assert entity_1.unique_id == f"{subentry_1.subentry_id}_signal_strength"
    assert entity_1.config_subentry_id == subentry_1.subentry_id

    entity_2 = entity_registry.async_get(entity_2.entity_id)
    assert entity_2
    assert entity_2.unique_id == subentry_2.subentry_id
    assert entity_2.config_subentry_id == subentry_2.subentry_id

    entity_3 = entity_registry.async_get(entity_3.entity_id)
    assert entity_3
    assert entity_3.unique_id == f"{subentry_1.subentry_id}_command"
    assert entity_3.config_subentry_id == subentry_1.subentry_id


async def test_migrate_entry_skips_foreign_and_migrated_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test migration leaves foreign and already-migrated entities alone.

    `async_entries_for_device` returns every entity attached to the device,
    including ones added by other integrations (e.g. a helper entity a user
    attached via the device page) and, on a retry after a partially
    completed migration, ones whose unique_id was already rewritten.
    """
    legacy_config = {
        "device": "abcd",
        "host": None,
        "port": None,
        "automatic_add": True,
        "protocols": [],
        "devices": {
            "0b1100cd0213c7f210010f51": {},
        },
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        data=legacy_config,
        subentries_data=(
            ConfigSubentryDataWithId(
                data={"event_code": "0b1100cd0213c7f210010f51"},
                subentry_type=SUBENTRY_TYPE_DEVICE,
                title="AC 213c7f2:16",
                unique_id="11_0_213c7f2:16",
                subentry_id="existing_subentry_id",
            ),
        ),
        version=1,
    )
    entry.add_to_hass(hass)

    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "11", "0", "213c7f2:16")},
    )

    # Already migrated in an earlier, interrupted attempt.
    migrated_entity = entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "existing_subentry_id_signal_strength",
        config_entry=entry,
        config_subentry_id="existing_subentry_id",
        device_id=device_1.id,
    )

    # A helper entity attached to the device by the user, owned by another
    # config entry.
    other_entry = MockConfigEntry(domain="other")
    other_entry.add_to_hass(hass)
    helper_entity = entity_registry.async_get_or_create(
        "sensor",
        "other",
        "helper_unique_id",
        config_entry=other_entry,
        device_id=device_1.id,
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 3

    migrated_entity = entity_registry.async_get(migrated_entity.entity_id)
    assert migrated_entity
    assert migrated_entity.unique_id == "existing_subentry_id_signal_strength"
    assert migrated_entity.config_subentry_id == "existing_subentry_id"

    helper_entity = entity_registry.async_get(helper_entity.entity_id)
    assert helper_entity
    assert helper_entity.unique_id == "helper_unique_id"
    assert helper_entity.config_entry_id == other_entry.entry_id
    assert helper_entity.config_subentry_id is None
