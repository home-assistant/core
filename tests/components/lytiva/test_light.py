"""Tests for Lytiva light platform."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
)
from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


class MockMessage:
    """Mock MQTT message."""

    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


@pytest.fixture
async def setup_lytiva(hass: HomeAssistant, mock_mqtt_client: MagicMock):
    """Set up Lytiva integration for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"broker": "192.168.1.100", "port": 1883},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lytiva.mqtt_client.Client",
        return_value=mock_mqtt_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Trigger on_connect to set up subscriptions
        mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 0)
        await hass.async_block_till_done()

    return entry


def get_discovery_callback(mock_mqtt_client: MagicMock):
    """Get the discovery callback from mock client."""
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in str(args[0]):
            return args[1]
    return None


def get_status_callback(mock_mqtt_client: MagicMock):
    """Get the status callback from mock client."""
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "STATUS" in str(args[0]):
            return args[1]
    return None


async def test_light_dimmer_discovery(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test dimmer light discovery."""
    # Send discovery message
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    assert discovery_callback is not None

    payload = {
        "unique_id": "dimmer_1",
        "name": "Test Dimmer",
        "type": "dimmer",
        "command_topic": "LYT/1/NODE/E/COMMAND",
        "address": 1,
    }

    msg = MockMessage(
        "homeassistant/light/dimmer_1/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Verify entity was created
    state = hass.states.get("light.test_dimmer")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes.get("supported_color_modes") == [ColorMode.BRIGHTNESS]


async def test_light_dimmer_turn_on(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test turning on a dimmer light."""
    # Discover light
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "dimmer_2",
        "name": "Dimmer 2",
        "type": "dimmer",
        "command_topic": "LYT/2/NODE/E/COMMAND",
        "address": 2,
    }
    msg = MockMessage(
        "homeassistant/light/dimmer_2/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Turn on with brightness
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.dimmer_2", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )

    # Verify MQTT publish was called
    assert mock_mqtt_client.publish.called
    call_args = mock_mqtt_client.publish.call_args[0]
    assert call_args[0] == "LYT/2/NODE/E/COMMAND"
    sent_payload = json.loads(call_args[1])
    assert sent_payload["address"] == 2
    assert sent_payload["type"] == "dimmer"
    assert sent_payload["dimming"] == 50  # 128/255 * 100


async def test_light_dimmer_turn_off(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test turning off a dimmer light."""
    # Discover and turn on light first
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "dimmer_3",
        "name": "Dimmer 3",
        "type": "dimmer",
        "command_topic": "LYT/3/NODE/E/COMMAND",
        "address": 3,
    }
    msg = MockMessage(
        "homeassistant/light/dimmer_3/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Turn off
    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.dimmer_3"},
        blocking=True,
    )

    # Verify MQTT publish
    call_args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(call_args[1])
    assert sent_payload["type"] == "dimmer"
    assert sent_payload["dimming"] == 0


async def test_light_cct_discovery(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test CCT light discovery."""
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "cct_1",
        "name": "CCT Light",
        "type": "cct",
        "command_topic": "LYT/10/NODE/E/COMMAND",
        "address": 10,
        "min_mireds": 150,
        "max_mireds": 370,
    }
    msg = MockMessage("homeassistant/light/cct_1/config", json.dumps(payload).encode())
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.cct_light")
    assert state is not None
    assert state.attributes.get("supported_color_modes") == [ColorMode.COLOR_TEMP]


async def test_light_cct_turn_on_with_color_temp(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test CCT light with color temperature."""
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "cct_2",
        "name": "CCT 2",
        "type": "cct",
        "command_topic": "LYT/11/NODE/E/COMMAND",
        "address": 11,
    }
    msg = MockMessage("homeassistant/light/cct_2/config", json.dumps(payload).encode())
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Turn on with color temp
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.cct_2",
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4000,
        },
        blocking=True,
    )

    # Verify publish
    call_args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(call_args[1])
    assert sent_payload["type"] == "cct"
    assert sent_payload["dimming"] == 100
    assert "color_temperature" in sent_payload


async def test_light_rgb_discovery(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test RGB light discovery."""
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "rgb_1",
        "name": "RGB Light",
        "type": "rgb",
        "command_topic": "LYT/20/NODE/E/COMMAND",
        "address": 20,
    }
    msg = MockMessage("homeassistant/light/rgb_1/config", json.dumps(payload).encode())
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    state = hass.states.get("light.rgb_light")
    assert state is not None
    assert state.attributes.get("supported_color_modes") == [ColorMode.RGB]


async def test_light_rgb_turn_on_with_color(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test RGB light with color."""
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "rgb_2",
        "name": "RGB 2",
        "type": "rgb",
        "command_topic": "LYT/21/NODE/E/COMMAND",
        "address": 21,
    }
    msg = MockMessage("homeassistant/light/rgb_2/config", json.dumps(payload).encode())
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Turn on with RGB color
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.rgb_2", ATTR_RGB_COLOR: (255, 0, 0)},
        blocking=True,
    )

    # Verify publish
    call_args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(call_args[1])
    assert sent_payload["type"] == "rgb"
    assert sent_payload["r"] == 255
    assert sent_payload["g"] == 0
    assert sent_payload["b"] == 0


async def test_light_status_update(
    hass: HomeAssistant, mock_mqtt_client: MagicMock, setup_lytiva
) -> None:
    """Test light status updates from MQTT."""
    # Discover light
    discovery_callback = get_discovery_callback(mock_mqtt_client)
    payload = {
        "unique_id": "dimmer_status",
        "name": "Status Test",
        "type": "dimmer",
        "command_topic": "LYT/30/NODE/E/COMMAND",
        "address": 30,
    }
    msg = MockMessage(
        "homeassistant/light/dimmer_status/config", json.dumps(payload).encode()
    )
    discovery_callback(mock_mqtt_client, None, msg)
    await hass.async_block_till_done()

    # Send status update
    status_callback = get_status_callback(mock_mqtt_client)
    assert status_callback is not None

    status_payload = {"address": 30, "dimming": 75}
    status_msg = MockMessage(
        "LYT/30/NODE/E/STATUS", json.dumps(status_payload).encode()
    )
    status_callback(mock_mqtt_client, None, status_msg)
    await hass.async_block_till_done()

    # Verify state was updated
    state = hass.states.get("light.status_test")
    assert state.state == STATE_ON
    # 75% dimming = 191 brightness (75/100 * 255)
    assert state.attributes[ATTR_BRIGHTNESS] == 191
