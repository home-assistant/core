"""Test ESPHome infrared proxy remotes."""

from unittest.mock import patch

from aioesphomeapi import (
    APIClient,
    InfraredProxyCapability,
    InfraredProxyInfo,
    InfraredProxyReceiveEvent,
)
import pytest

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN, RemoteEntityFeature
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


async def test_infrared_proxy_transmitter_only(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test an infrared proxy remote with transmitter capability only."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test initial state
    state = hass.states.get("remote.test_my_remote")
    assert state is not None
    assert state.state == STATE_ON
    # Transmitter-only should not support learn
    assert state.attributes["supported_features"] == 0


async def test_infrared_proxy_receiver_capability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test an infrared proxy remote with receiver capability."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER
            | InfraredProxyCapability.RECEIVER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test initial state
    state = hass.states.get("remote.test_my_remote")
    assert state is not None
    assert state.state == STATE_ON
    # Should support learn command
    assert state.attributes["supported_features"] == RemoteEntityFeature.LEARN_COMMAND


async def test_infrared_proxy_unavailability(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test infrared proxy remote availability."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER,
        )
    ]
    states = []
    user_service = []
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test initial state
    state = hass.states.get("remote.test_my_remote")
    assert state is not None
    assert state.state == STATE_ON

    # Test device becomes unavailable
    await device.mock_disconnect(True)
    await hass.async_block_till_done()
    state = hass.states.get("remote.test_my_remote")
    assert state.state == STATE_UNAVAILABLE

    # Test device becomes available again
    await device.mock_connect()
    await hass.async_block_till_done()
    state = hass.states.get("remote.test_my_remote")
    assert state.state == STATE_ON


async def test_infrared_proxy_receive_event(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test infrared proxy receive event firing."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.RECEIVER,
        )
    ]
    states = []
    user_service = []
    device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
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
    # Get entry_data from the config entry
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


async def test_infrared_proxy_send_command_protocol(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test sending protocol-based commands."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test protocol-based command
    with patch.object(
        mock_client, "infrared_proxy_transmit_protocol"
    ) as mock_transmit_protocol:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {
                "entity_id": "remote.test_my_remote",
                "command": ['{"protocol": "NEC", "address": 4, "command": 8}'],
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        mock_transmit_protocol.assert_called_once_with(
            1, '{"protocol": "NEC", "address": 4, "command": 8}'
        )


async def test_infrared_proxy_send_command_pulse_width(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test sending pulse-width based commands."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test pulse-width command
    with patch.object(mock_client, "infrared_proxy_transmit") as mock_transmit:
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {
                "entity_id": "remote.test_my_remote",
                "command": [
                    '{"timing": {"frequency": 38000, "length_in_bits": 32}, "data": [1, 2, 3, 4]}'
                ],
            },
            blocking=True,
        )
        await hass.async_block_till_done()

        assert mock_transmit.call_count == 1
        call_args = mock_transmit.call_args
        assert call_args[0][0] == 1  # key
        assert call_args[0][2] == b"\x01\x02\x03\x04"  # decoded data


async def test_infrared_proxy_send_command_invalid_json(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test sending invalid JSON command."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test invalid JSON
    with pytest.raises(
        ServiceValidationError,
        match="Command must be valid JSON",
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {"entity_id": "remote.test_my_remote", "command": ["not valid json"]},
            blocking=True,
        )


async def test_infrared_proxy_send_command_invalid_data_array(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test sending command with invalid data array."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.TRANSMITTER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test invalid data type (not an array)
    with pytest.raises(
        ServiceValidationError,
        match="Data must be an array of integers",
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {
                "entity_id": "remote.test_my_remote",
                "command": ['{"timing": {"frequency": 38000}, "data": "not_an_array"}'],
            },
            blocking=True,
        )

    # Test invalid array values (out of range)
    with pytest.raises(
        ServiceValidationError,
        match="Invalid data array",
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {
                "entity_id": "remote.test_my_remote",
                "command": ['{"timing": {"frequency": 38000}, "data": [1, 2, 300, 4]}'],
            },
            blocking=True,
        )


async def test_infrared_proxy_send_command_no_transmitter(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test sending command to receiver-only device."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.RECEIVER,  # No transmitter
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test send_command raises error
    with pytest.raises(
        HomeAssistantError,
        match="does not support infrared transmission",
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {
                "entity_id": "remote.test_my_remote",
                "command": ['{"protocol": "NEC", "address": 4, "command": 8}'],
            },
            blocking=True,
        )


async def test_infrared_proxy_learn_command_not_implemented(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test that learn_command raises appropriate error."""
    entity_info = [
        InfraredProxyInfo(
            object_id="myremote",
            key=1,
            name="my remote",
            capabilities=InfraredProxyCapability.RECEIVER,
        )
    ]
    states = []
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    await hass.async_block_till_done()

    # Test learn_command raises error
    with pytest.raises(
        HomeAssistantError,
        match="Learning commands is handled automatically",
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "learn_command",
            {"entity_id": "remote.test_my_remote"},
            blocking=True,
        )
