"""The tests for the Rfxtrx component."""

from __future__ import annotations

from unittest.mock import ANY, call

import RFXtrx as rfxtrxmod

from homeassistant.components.rfxtrx.const import EVENT_RFXTRX_EVENT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import setup_rfx_test_cfg

from tests.typing import WebSocketGenerator

SOME_PROTOCOLS = ["ac", "arc"]


async def test_fire_event(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, rfxtrx
) -> None:
    """Test fire event."""
    await setup_rfx_test_cfg(
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

    device_id_1 = device_registry.async_get_device(
        identifiers={("rfxtrx", "11", "0", "213c7f2:16")}
    )
    assert device_id_1

    device_id_2 = device_registry.async_get_device(
        identifiers={("rfxtrx", "16", "0", "00:90")}
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
        "rfxtrx", "send", {"event": "0a520802060101ff0f0269"}, blocking=True
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

    device_id = ["11", "0", "213c7f2:16"]
    mock_entry = await setup_rfx_test_cfg(
        hass,
        devices={
            "0b1100cd0213c7f210010f51": {"fire_event": True, "device_id": device_id},
        },
    )

    device_entry = device_registry.async_get_device(
        identifiers={("rfxtrx", *device_id)}
    )
    assert device_entry

    # Ask to remove existing device
    client = await hass_ws_client(hass)
    response = await client.remove_device(device_entry.id, mock_entry.entry_id)
    assert response["success"]

    # Verify device entry is removed
    assert (
        device_registry.async_get_device(identifiers={("rfxtrx", *device_id)}) is None
    )

    # Verify that the config entry has removed the device
    assert mock_entry.data["devices"] == {}


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
