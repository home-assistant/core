"""Tests for Lytiva light platform with full logic coverage."""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_RGB_COLOR,
    ColorMode,
)
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
    """Mock Paho MQTT message."""
    def __init__(self, topic: str, payload: str | bytes):
        self.topic = topic
        self.payload = payload


async def trigger_discovery(
    mock_mqtt_client: MagicMock, topic: str, payload: dict[str, Any]
) -> None:
    """Trigger the dicovery callback on the mock client."""
    # Find the callback registered with message_callback_add for config topics
    # We look for the call args for subscribe/callback_add that match our topic pattern
    # The integration does: client.message_callback_add(f"{discovery_prefix}/+/+/config", on_discovery)
    
    # In __init__.py, on_connect is what sets this up.
    # If the test triggered on_connect, then message_callback_add was called.
    # We find the callback passed to it.
    
    callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "config" in args[0]:
            callback = args[1]
            break
            
    if callback:
        msg = MockMessage(topic, json.dumps(payload).encode("utf-8"))
        callback(mock_mqtt_client, None, msg)


async def trigger_status(
    mock_mqtt_client: MagicMock, topic: str, payload: dict[str, Any]
) -> None:
    """Trigger the status callback."""
    # Integration does: client.message_callback_add("LYT/+/NODE/E/STATUS", on_status)
    callback = None
    for call in mock_mqtt_client.message_callback_add.call_args_list:
        args, _ = call
        if "STATUS" in args[0]:
            callback = args[1]
            # Just take the first one found, typically on_status is the same function
            break
            
    if callback:
        msg = MockMessage(topic, json.dumps(payload).encode("utf-8"))
        # on_status schedules a coroutine, so it returns immediately
        callback(mock_mqtt_client, None, msg)


async def setup_integration(hass, mock_mqtt_client):
    """Setup the integration with mocked mqtt."""
    entry = MockConfigEntry(
        domain="lytiva",
        data={"broker": "1.2.3.4", "port": 1883},
    )
    entry.add_to_hass(hass)
    
    with patch("homeassistant.components.lytiva.mqtt_client.Client", return_value=mock_mqtt_client):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        
        # Trigger on_connect to register callbacks
        if hasattr(mock_mqtt_client, "on_connect"):
             mock_mqtt_client.on_connect(mock_mqtt_client, None, {}, 0)
        await hass.async_block_till_done()
    
    return entry


async def test_light_dimmer(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test dimmer light discovery and control."""
    await setup_integration(hass, mock_mqtt_client)

    # 1. Discovery
    payload = {
        "unique_id": "dimmer_1",
        "name": "Living Room Dimmer",
        "type": "dimmer",
        "command_topic": "LYT/1/NODE/E/COMMAND",
        "address": 1
    }
    await trigger_discovery(hass, mock_mqtt_client, "homeassistant/light/dimmer_1/config", payload)
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_dimmer")
    assert state
    assert state.state == STATE_OFF
    assert state.attributes.get("supported_color_modes") == [ColorMode.BRIGHTNESS]

    # 2. Turn On
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "light.living_room_dimmer", ATTR_BRIGHTNESS: 128},
        blocking=True,
    )
    
    # Check MQTT publish
    mock_mqtt_client.publish.assert_called_with(
        "LYT/1/NODE/E/COMMAND",
        json.dumps({"version": "v1.0", "address": 1, "type": "dimmer", "dimming": 50})
    )

    # 3. Status Update
    status_payload = {"address": 1, "dimming": 100}
    await trigger_status(hass, mock_mqtt_client, "LYT/1/NODE/E/STATUS", status_payload)
    await hass.async_block_till_done()

    state = hass.states.get("light.living_room_dimmer")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 255


async def test_light_cct(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test CCT light discovery and control."""
    await setup_integration(hass, mock_mqtt_client)
    
    # 1. Discovery
    payload = {
        "unique_id": "cct_1",
        "name": "Bedroom CCT",
        "type": "cct",
        "command_topic": "LYT/2/NODE/E/COMMAND",
        "address": 2,
        "min_mireds": 150,
        "max_mireds": 370
    }
    await trigger_discovery(hass, mock_mqtt_client, "homeassistant/light/cct_1/config", payload)
    await hass.async_block_till_done()
    
    state = hass.states.get("light.bedroom_cct")
    assert state
    assert state.attributes.get("supported_color_modes") == [ColorMode.COLOR_TEMP]

    # 2. Turn On with Color Temp
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.bedroom_cct", 
            ATTR_BRIGHTNESS: 255,
            ATTR_COLOR_TEMP_KELVIN: 4000
        },
        blocking=True,
    )
    
    # Verify publish logic: kelvin -> mired conversion -> scaling
    # 4000K = 250 mireds
    # Range 150-370. Span = 220.
    # Scaled = (250 - 150) * 100 / 220 = 45.45 => 45
    # Device uses inverted: 100 - 45 = 55
    
    args = mock_mqtt_client.publish.call_args[0]
    sent_payload = json.loads(args[1])
    assert sent_payload["type"] == "cct"
    assert sent_payload["dimming"] == 100
    # Allow some tolerance for rounding
    assert 54 <= sent_payload["color_temperature"] <= 56


async def test_light_rgb(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test RGB light discovery and control."""
    await setup_integration(hass, mock_mqtt_client)
    
    # 1. Discovery
    payload = {
        "unique_id": "rgb_1",
        "name": "Garden RGB",
        "type": "rgb",
        "command_topic": "LYT/3/NODE/E/COMMAND",
        "address": 3
    }
    await trigger_discovery(hass, mock_mqtt_client, "homeassistant/light/rgb_1/config", payload)
    await hass.async_block_till_done()
    
    state = hass.states.get("light.garden_rgb")
    assert state.attributes.get("supported_color_modes") == [ColorMode.RGB]

    # 2. Turn On RGB
    await hass.services.async_call(
        "light",
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: "light.garden_rgb", 
            ATTR_RGB_COLOR: (255, 0, 0)
        },
        blocking=True,
    )
    
    mock_mqtt_client.publish.assert_called_with(
        "LYT/3/NODE/E/COMMAND",
        json.dumps({"version": "v1.0", "address": 3, "type": "rgb", "r": 255, "g": 0, "b": 0})
    )

    # 3. Turn Off
    await hass.services.async_call(
        "light",
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "light.garden_rgb"},
        blocking=True,
    )
    
    mock_mqtt_client.publish.assert_called_with(
        "LYT/3/NODE/E/COMMAND",
        json.dumps({"version": "v1.0", "address": 3, "type": "rgb", "r": 0, "g": 0, "b": 0})
    )


async def test_light_turn_off_dimmer(hass: HomeAssistant, mock_mqtt_client: MagicMock) -> None:
    """Test turning off a dimmer."""
    await setup_integration(hass, mock_mqtt_client)
    
    # Discovery
    await trigger_discovery(hass, mock_mqtt_client, "ha/light/d2/config", {
        "unique_id": "d2", "type": "dimmer", "address": 4, "command_topic": "CMD"
    })
    await hass.async_block_till_done()

    # Turn Off
    await hass.services.async_call(
        "light", SERVICE_TURN_OFF, {ATTR_ENTITY_ID: "light.lytiva_light"}, blocking=True
    )
    
    mock_mqtt_client.publish.assert_called_with(
        "CMD",
        json.dumps({"version": "v1.0", "address": 4, "type": "dimmer", "dimming": 0})
    )
