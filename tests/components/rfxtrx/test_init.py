"""The tests for the Rfxtrx component."""

from unittest.mock import ANY, call

import RFXtrx as rfxtrxmod

from homeassistant.components.rfxtrx import DOMAIN, DeviceTuple
from homeassistant.components.rfxtrx.const import EVENT_RFXTRX_EVENT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

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
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={
            (DOMAIN, "16", "0", "00:90"),
        },
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

    await entry.async_migrate(hass)

    assert dict(entry.data) == {
        "device": "abcd",
        "host": None,
        "port": None,
        "automatic_add": True,
        "protocols": [],
    }
    assert entry.version == 2

    subentries = {
        subentry.unique_id: subentry for subentry in entry.subentries.values()
    }
    assert subentries.keys() == {"11_0_213c7f2:16", "16_0_00:90"}

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

    entity_1 = entity_registry.async_get(entity_1.entity_id)
    assert entity_1
    assert entity_1.unique_id == f"{subentry_1.subentry_id}_signal_strength"
    assert entity_1.config_subentry_id == subentry_1.subentry_id

    entity_2 = entity_registry.async_get(entity_2.entity_id)
    assert entity_2
    assert entity_2.unique_id == subentry_2.subentry_id
    assert entity_2.config_subentry_id == subentry_2.subentry_id
