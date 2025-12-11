"""Tests for Lytiva light platform."""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
)
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant


class MockMessage:
    """Mock MQTT message."""

    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


def trigger_discovery(mock_mqtt_client: MagicMock, topic: str, payload: dict):
    """Trigger discovery callback."""
    # Find the discovery callback
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in str(args[0]):
            callback = args[1]
            msg = MockMessage(topic, json.dumps(payload).encode())
            callback(mock_mqtt_client, None, msg)
            return
    raise AssertionError("Discovery callback not found")


async def trigger_status(hass: HomeAssistant, mock_mqtt_client: MagicMock, topic: str, payload: dict):
    """Trigger status callback."""
    # Find the status callback
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "STATUS" in str(args[0]):
            callback = args[1]
            msg = MockMessage(topic, json.dumps(payload).encode())
            callback(mock_mqtt_client, None, msg)
            await hass.async_block_till_done()
            return
    raise AssertionError("Status callback not found")


async def test_light_dimmer_discovery(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test dimmer light discovery and creation."""
    payload = {
        "unique_id": "dimmer_1",
        "name": "Test Dimmer",
        "type": "dimmer",
        "command_topic": "LYT/1/NODE/E/COMMAND",
        "address": 1,
    }

    trigger_discovery(mock_mqtt_client, "homeassistant/light/dimmer_1/config", payload)
    await hass.async_block_till_done()

    state = hass.states.get("light.test_dimmer")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get("supported_color_modes") == [ColorMode.BRIGHTNESS]


async def test_light_dimmer_turn_on(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test turning on a dimmer light."""
    # Discover light
    payload = {
        "unique_id": "dimmer_2",
        "name": "Dimmer 2",
        "type": "dimmer",
        "command_topic": "LYT/2/NODE/E/COMMAND",
        "address": 2,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/dimmer_2/config", payload)
    await hass.async_block_till_done()

    # Reset mock to clear previous calls
    mock_mqtt_client.publish.reset_mock()

    # Turn on with brightness
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": "light.dimmer_2", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    # Verify MQTT publish was called with correct payload
    assert mock_mqtt_client.publish.called
    call_args = mock_mqtt_client.publish.call_args[0]
    assert call_args[0] == "LYT/2/NODE/E/COMMAND"
    sent_payload = json.loads(call_args[1])
    assert sent_payload["address"] == 2
    assert sent_payload["type"] == "dimmer"
    assert 49 <= sent_payload["dimming"] <= 51  # ~50% (128/255 * 100)


async def test_light_dimmer_turn_off(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test turning off a dimmer light."""
    # Discover light
    payload = {
        "unique_id": "dimmer_3",
        "name": "Dimmer 3",
        "type": "dimmer",
        "command_topic": "LYT/3/NODE/E/COMMAND",
        "address": 3,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/dimmer_3/config", payload)
    await hass.async_block_till_done()

    mock_mqtt_client.publish.reset_mock()

    # Turn off
    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {"entity_id": "light.dimmer_3"},
        blocking=True,
    )

    # Verify MQTT publish
    assert mock_mqtt_client.publish.called
    call_args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(call_args[1])
    assert sent_payload["type"] == "dimmer"
    assert sent_payload["dimming"] == 0


async def test_light_cct_discovery(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test CCT light discovery."""
    payload = {
        "unique_id": "cct_1",
        "name": "CCT Light",
        "type": "cct",
        "command_topic": "LYT/10/NODE/E/COMMAND",
        "address": 10,
        "min_mireds": 150,
        "max_mireds": 370,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/cct_1/config", payload)
    await hass.async_block_till_done()

    state = hass.states.get("light.cct_light")
    assert state is not None
    assert state.attributes.get("supported_color_modes") == [ColorMode.COLOR_TEMP]


async def test_light_cct_turn_on_with_color_temp(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test CCT light with color temperature."""
    payload = {
        "unique_id": "cct_2",
        "name": "CCT 2",
        "type": "cct",
        "command_topic": "LYT/11/NODE/E/COMMAND",
        "address": 11,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/cct_2/config", payload)
    await hass.async_block_till_done()

    mock_mqtt_client.publish.reset_mock()

    # Turn on with color temp
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            "entity_id": "light.cct_2",
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4000,
        },
        blocking=True,
    )

    # Verify publish
    assert mock_mqtt_client.publish.called
    call_args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(call_args[1])
    assert sent_payload["type"] == "cct"
    assert sent_payload["dimming"] == 100
    assert "color_temperature" in sent_payload


async def test_light_rgb_discovery(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test RGB light discovery."""
    payload = {
        "unique_id": "rgb_1",
        "name": "RGB Light",
        "type": "rgb",
        "command_topic": "LYT/20/NODE/E/COMMAND",
        "address": 20,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/rgb_1/config", payload)
    await hass.async_block_till_done()

    state = hass.states.get("light.rgb_light")
    assert state is not None
    assert state.attributes.get("supported_color_modes") == [ColorMode.RGB]


async def test_light_rgb_turn_on_with_color(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test RGB light with color."""
    payload = {
        "unique_id": "rgb_2",
        "name": "RGB 2",
        "type": "rgb",
        "command_topic": "LYT/21/NODE/E/COMMAND",
        "address": 21,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/rgb_2/config", payload)
    await hass.async_block_till_done()

    mock_mqtt_client.publish.reset_mock()

    # Turn on with RGB color
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {"entity_id": "light.rgb_2", ATTR_RGB_COLOR: (255, 0, 0)},
        blocking=True,
    )

    # Verify publish
    assert mock_mqtt_client.publish.called
    call_args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(call_args[1])
    assert sent_payload["type"] == "rgb"
    assert sent_payload["r"] == 255
    assert sent_payload["g"] == 0
    assert sent_payload["b"] == 0


async def test_light_status_update(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test light status updates from MQTT."""
    # Discover light
    payload = {
        "unique_id": "dimmer_status",
        "name": "Status Test",
        "type": "dimmer",
        "command_topic": "LYT/30/NODE/E/COMMAND",
        "address": 30,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/dimmer_status/config", payload)
    await hass.async_block_till_done()

    # Send status update
    status_payload = {"address": 30, "dimming": 75}
    await trigger_status(hass, mock_mqtt_client, "LYT/30/NODE/E/STATUS", status_payload)

    # Verify state was updated
    state = hass.states.get("light.status_test")
    assert state is not None
    assert state.state == STATE_ON
    # 75% dimming = 191 brightness (75/100 * 255)
    assert state.attributes[ATTR_BRIGHTNESS] == 191


async def test_light_device_info(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test light device info."""
    payload = {
        "unique_id": "light_device",
        "name": "Device Test",
        "type": "dimmer",
        "command_topic": "LYT/40/NODE/E/COMMAND",
        "address": 40,
        "device": {
            "identifiers": ["lytiva_device_1"],
            "name": "Lytiva Device 1",
            "manufacturer": "Lytiva",
            "model": "Smart Light",
            "suggested_area": "Living Room",
        },
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/light_device/config", payload)
    await hass.async_block_till_done()

    state = hass.states.get("light.device_test")
    assert state is not None


async def test_light_cct_status_update(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test CCT light status update."""
    payload = {
        "unique_id": "cct_status",
        "name": "CCT Status",
        "type": "cct",
        "command_topic": "LYT/50/NODE/E/COMMAND",
        "address": 50,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/cct_status/config", payload)
    await hass.async_block_till_done()

    # Send status with color temp
    status_payload = {
        "address": 50,
        "cct": {"dimming": 80, "color_temperature": 50},
    }
    await trigger_status(hass, mock_mqtt_client, "LYT/50/NODE/E/STATUS", status_payload)

    state = hass.states.get("light.cct_status")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 204  # 80/100 * 255


async def test_light_rgb_status_update(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_integration
) -> None:
    """Test RGB light status update."""
    payload = {
        "unique_id": "rgb_status",
        "name": "RGB Status",
        "type": "rgb",
        "command_topic": "LYT/60/NODE/E/COMMAND",
        "address": 60,
    }
    trigger_discovery(mock_mqtt_client, "homeassistant/light/rgb_status/config", payload)
    await hass.async_block_till_done()

    # Send RGB status
    status_payload = {"address": 60, "rgb": {"r": 100, "g": 150, "b": 200}}
    await trigger_status(hass, mock_mqtt_client, "LYT/60/NODE/E/STATUS", status_payload)

    state = hass.states.get("light.rgb_status")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_RGB_COLOR] == (100, 150, 200)
