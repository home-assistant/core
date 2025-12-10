"""Test ESPHome infrared proxy remotes."""

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
from homeassistant.exceptions import HomeAssistantError


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


async def test_infrared_proxy_send_command_not_implemented(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device,
) -> None:
    """Test that send_command raises appropriate error."""
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

    # Test send_command raises error
    with pytest.raises(
        HomeAssistantError,
        match="Direct command sending not yet implemented",
    ):
        await hass.services.async_call(
            REMOTE_DOMAIN,
            "send_command",
            {"entity_id": "remote.test_my_remote", "command": ["test"]},
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
