"""Test ESPHome infrared platform."""

from unittest.mock import patch

from aioesphomeapi import (
    APIClient,
    InfraredProxyCapability,
    InfraredProxyInfo,
    InfraredProxyReceiveEvent,
)
import pytest

from homeassistant.components.infrared import (
    InfraredEntityFeature,
    NECInfraredCommand,
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


def _get_expected_entity_id(capabilities: InfraredProxyCapability) -> str:
    """Get expected entity ID based on capabilities.

    The entity name is dynamically determined in the entity based on capabilities:
    - TRANSMITTER only -> "IR Transmitter" -> infrared.test_ir_transmitter
    - RECEIVER only -> "IR Receiver" -> infrared.test_ir_receiver
    - Both -> "IR Transceiver" -> infrared.test_ir_transceiver
    """
    if capabilities == InfraredProxyCapability.TRANSMITTER:
        return "infrared.test_ir_transmitter"
    if capabilities == InfraredProxyCapability.RECEIVER:
        return "infrared.test_ir_receiver"
    return "infrared.test_ir_transceiver"


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

    entity_id = _get_expected_entity_id(capabilities)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("supported_features") == expected_features


async def test_unavailability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test infrared entity availability."""
    entity_info = [_create_infrared_proxy_info()]
    device = await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    entity_id = "infrared.test_ir_transmitter"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE

    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    await device.mock_connect()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
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


async def test_send_nec_command(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test sending NEC command via native API using raw timings."""
    entity_info = [_create_infrared_proxy_info()]
    await mock_esphome_device(mock_client=mock_client, entity_info=entity_info)
    await hass.async_block_till_done()

    entities = async_get_entities(
        hass, supported_features=InfraredEntityFeature.TRANSMIT
    )
    assert len(entities) == 1
    entity = entities[0]

    command = NECInfraredCommand(
        address=0x10,
        command=0x20,
        repeat_count=1,
    )

    with patch.object(
        mock_client, "infrared_proxy_transmit_raw_timings"
    ) as mock_transmit:
        await entity.async_send_command(command)
        await hass.async_block_till_done()

        mock_transmit.assert_called_once()
        call_args = mock_transmit.call_args
        assert call_args[0][0] == 1  # key

        # Verify carrier frequency
        assert call_args.kwargs.get("carrier_frequency") == 38000

        # Verify timings is a list of integers (alternating high/low)
        timings = call_args.kwargs.get("timings")
        assert timings is not None
        assert isinstance(timings, list)
        assert len(timings) > 0
        # Should have alternating positive (high) and negative (low) values
        # First should be positive (leader high)
        assert timings[0] > 0


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

    entities = async_get_entities(
        hass, supported_features=InfraredEntityFeature.RECEIVE
    )
    assert len(entities) == 1
    entity = entities[0]

    command = NECInfraredCommand(address=0x04, command=0x08)

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

    entry = entity_registry.async_get("infrared.test_ir_transmitter")
    assert entry is not None
    assert entry.device_id == device.id
