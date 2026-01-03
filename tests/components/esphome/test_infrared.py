"""Test ESPHome infrared platform."""

import json
from unittest.mock import patch

from aioesphomeapi import (
    APIClient,
    InfraredProxyCapability,
    InfraredProxyInfo,
    InfraredProxyReceiveEvent,
)
import pytest

from homeassistant.components.infrared import (
    InfraredCommand,
    InfraredEntityFeature,
    InfraredProtocolType,
    IRTiming,
    NECInfraredCommand,
    PulseWidthInfraredCommand,
    PulseWidthIRProtocol,
    SamsungInfraredCommand,
    async_get_entities,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockESPHomeDeviceType


def _create_infrared_proxy_info(
    object_id: str = "myremote",
    key: int = 1,
    name: str = "my remote",
    capabilities: InfraredProxyCapability = InfraredProxyCapability.TRANSMITTER,
) -> InfraredProxyInfo:
    """Create mock InfraredProxyInfo."""
    return InfraredProxyInfo(
        object_id=object_id, key=key, name=name, capabilities=capabilities
    )


@pytest.mark.parametrize(
    ("capabilities", "expected_features"),
    [
        (InfraredProxyCapability.TRANSMITTER, InfraredEntityFeature.TRANSMIT),
        (
            InfraredProxyCapability.RECEIVER,
            InfraredEntityFeature.RECEIVE,
        ),
        (
            InfraredProxyCapability.TRANSMITTER | InfraredProxyCapability.RECEIVER,
            InfraredEntityFeature.TRANSMIT | InfraredEntityFeature.RECEIVE,
        ),
    ],
)
async def test_capabilities(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    capabilities: InfraredProxyCapability,
    expected_features: InfraredEntityFeature,
) -> None:
    """Test infrared entity capabilities."""
    entity_info = [_create_infrared_proxy_info(capabilities=capabilities)]
    await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    state = hass.states.get("infrared.test_my_remote")
    assert state is not None
    assert state.attributes.get("supported_features") == expected_features


async def test_supported_protocols(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test infrared entity supported protocols."""
    entity_info = [_create_infrared_proxy_info()]
    await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    state = hass.states.get("infrared.test_my_remote")
    assert state is not None
    protocols = state.attributes.get("supported_protocols")
    assert protocols is not None
    assert InfraredProtocolType.NEC.value in protocols
    assert InfraredProtocolType.PULSE_WIDTH.value in protocols
    assert InfraredProtocolType.SAMSUNG.value in protocols


async def test_unavailability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test infrared entity availability."""
    entity_info = [_create_infrared_proxy_info()]
    device = await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    state = hass.states.get("infrared.test_my_remote")
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get("infrared.test_my_remote")
    assert state.state == STATE_UNAVAILABLE

    await device.mock_connect()
    await hass.async_block_till_done()
    state = hass.states.get("infrared.test_my_remote")
    assert state.state != STATE_UNAVAILABLE


async def test_receive_event(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test infrared receive event firing."""
    entity_info = [
        _create_infrared_proxy_info(capabilities=InfraredProxyCapability.RECEIVER)
    ]
    device = await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    events = []

    def event_listener(event):
        events.append(event)

    hass.bus.async_listen("esphome_infrared_proxy_received", event_listener)

    # Simulate receiving an infrared signal
    receive_event = InfraredProxyReceiveEvent(
        key=1,
        timings=[1000, 500, 1000, 500, 500, 1000],
    )
    entry_data = device.entry.runtime_data
    entry_data.async_on_infrared_proxy_receive(hass, receive_event)
    await hass.async_block_till_done()

    # Verify event was fired
    assert len(events) == 1
    event_data = events[0].data
    assert event_data["key"] == 1
    assert event_data["timings"] == [1000, 500, 1000, 500, 500, 1000]
    assert event_data["device_name"] == "test"
    assert "entry_id" in event_data


@pytest.mark.parametrize(
    ("command", "expected_json"),
    [
        (
            NECInfraredCommand(
                repeat_count=1,
                address=0x10,
                command=0x20,
            ),
            {"protocol": "nec", "address": 0x10, "command": 0x20, "repeat": 1},
        ),
        (
            SamsungInfraredCommand(
                repeat_count=2,
                code=0xE0E040BF,
                length_in_bits=32,
            ),
            {"protocol": "samsung", "data": 0xE0E040BF, "nbits": 32, "repeat": 2},
        ),
    ],
)
async def test_send_nec_command(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    command: InfraredCommand,
    expected_json: dict,
) -> None:
    """Test sending command via native API."""
    entity_info = [_create_infrared_proxy_info()]
    await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    entities = async_get_entities(hass)
    assert len(entities) == 1
    entity = entities[0]

    with patch.object(mock_client, "infrared_proxy_transmit_protocol") as mock_transmit:
        await entity.async_send_command(command)
        await hass.async_block_till_done()

        mock_transmit.assert_called_once()
        call_args = mock_transmit.call_args
        assert call_args[0][0] == 1  # key

        cmd_json = json.loads(call_args[0][1])
        assert cmd_json == expected_json


async def test_send_pulse_width_command(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending pulse-width command via native API."""
    entity_info = [_create_infrared_proxy_info()]
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=[],
        states=[],
    )
    await hass.async_block_till_done()

    entities = async_get_entities(hass)
    assert len(entities) == 1
    entity = entities[0]

    protocol = PulseWidthIRProtocol(
        header=IRTiming(high_us=9000, low_us=4500),
        one=IRTiming(high_us=560, low_us=1690),
        zero=IRTiming(high_us=560, low_us=560),
        footer=IRTiming(high_us=560, low_us=0),
        frequency=38000,
        msb_first=False,
    )
    command = PulseWidthInfraredCommand(
        protocol=protocol, repeat_count=1, code=0x20DF10EF, length_in_bits=32
    )

    with patch.object(mock_client, "infrared_proxy_transmit") as mock_transmit:
        await entity.async_send_command(command)
        await hass.async_block_till_done()

        mock_transmit.assert_called_once()
        call_args = mock_transmit.call_args
        assert call_args[0][0] == 1  # key
        # Timing params should be second argument
        timing = call_args[0][1]
        assert timing.frequency == 38000
        assert timing.length_in_bits == 32
        # Data bytes should be third argument
        data_bytes = call_args[0][2]
        assert isinstance(data_bytes, bytes)
        assert len(data_bytes) == 4


async def test_send_command_no_transmitter(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending command to receiver-only device raises error."""
    entity_info = [
        _create_infrared_proxy_info(capabilities=InfraredProxyCapability.RECEIVER)
    ]
    await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    entities = async_get_entities(hass)
    assert len(entities) == 1
    entity = entities[0]

    command = NECInfraredCommand(repeat_count=1, address=0x04, command=0x08)

    with pytest.raises(HomeAssistantError):
        await entity.async_send_command(command)


async def test_device_association(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test infrared entity is associated with ESPHome device."""
    entity_info = [_create_infrared_proxy_info()]
    await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:aa")}
    )
    assert device is not None

    entry = entity_registry.async_get("infrared.test_my_remote")
    assert entry is not None
    assert entry.device_id == device.id
