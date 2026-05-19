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
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import async_fire_mqtt_message


class MockMsg:
    """Mock MQTT message."""

    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload


async def async_discover_light(hass, mqtt_mock, payload):
    """Helper to trigger light discovery via MQTT."""
    for call in mqtt_mock.async_subscribe.call_args_list:
        if any("LYT/homeassistant/+/+/config" in str(arg) for arg in call[0]):
            for arg in reversed(call[0]):
                if callable(arg):
                    await arg(MockMsg(f"LYT/homeassistant/light/{payload['unique_id']}/config", json.dumps(payload)))
                    await hass.async_block_till_done()
                    return


def get_sent_payload(mqtt_mock, topic):
    """Helper to get the last sent payload for a topic."""
    for call in reversed(mqtt_mock.async_publish.call_args_list):
        if call[0][0] == topic:
            return json.loads(call[0][1])
    return None


async def test_light_dimmer_discovery(hass, mqtt_mock, setup_integration):
    """Test dimmer light discovery."""
    payload = {"unique_id": "d1", "name": "Dimmer", "type": "dimmer", "address": 1}
    await async_discover_light(hass, mqtt_mock, payload)
    state = hass.states.get("light.dimmer")
    assert state and state.attributes.get("supported_color_modes") == [ColorMode.BRIGHTNESS]


async def test_light_dimmer_turn_on(hass, mqtt_mock, setup_integration):
    """Test turning on a dimmer light."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "d2", "name": "D2", "type": "dimmer", "command_topic": "L/2/C", "address": 2})
    await hass.services.async_call("light", SERVICE_TURN_ON, {"entity_id": "light.d2", ATTR_BRIGHTNESS: 128}, blocking=True)
    sent = get_sent_payload(mqtt_mock, "L/2/C")
    assert sent["dimming"] == 50
    assert sent["type"] == "dimmer"
    assert "state" not in sent


async def test_light_cct_discovery(hass, mqtt_mock, setup_integration):
    """Test CCT light discovery."""
    async_dispatcher_send(hass, f"{DOMAIN}_discovery_light", {"unique_id": "c1", "name": "CCT", "type": "cct", "address": 10})
    await hass.async_block_till_done()
    assert hass.states.get("light.cct").attributes.get("supported_color_modes") == [ColorMode.COLOR_TEMP]


async def test_light_rgb_discovery(hass, mqtt_mock, setup_integration):
    """Test RGB light discovery."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "r1", "name": "RGB", "type": "rgb", "address": 20})
    assert hass.states.get("light.rgb").attributes.get("supported_color_modes") == [ColorMode.RGB]


async def test_light_status_update(hass, mqtt_mock, setup_integration):
    """Test status updates."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "s1", "name": "S1", "type": "dimmer", "address": 30})
    # Updated nested status format
    async_fire_mqtt_message(hass, "LYT/homeassistant/30/status", json.dumps({"address": 30, "type": "dimmer", "dimmer": {"dimming": 75}}))
    await hass.async_block_till_done()
    assert hass.states.get("light.s1").attributes[ATTR_BRIGHTNESS] == 191


async def test_light_device_info(hass, mqtt_mock, setup_integration):
    """Test device info."""
    payload = {"unique_id": "di1", "name": "DI1", "address": 40, "device": {"identifiers": ["id1"], "manufacturer": "M1"}}
    await async_discover_light(hass, mqtt_mock, payload)
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "id1")})
    assert device and device.manufacturer == "M1"


async def test_light_cct_turn_on(hass, mqtt_mock, setup_integration):
    """Test CCT turn on."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "c2", "name": "C2", "type": "cct", "command_topic": "L/11/C", "address": 11})
    await hass.services.async_call("light", SERVICE_TURN_ON, {"entity_id": "light.c2", ATTR_COLOR_TEMP_KELVIN: 3000}, blocking=True)
    sent = get_sent_payload(mqtt_mock, "L/11/C")
    assert sent["type"] == "cct"
    assert "color_temperature" in sent
    assert "state" not in sent


async def test_light_rgb_turn_on(hass, mqtt_mock, setup_integration):
    """Test RGB turn on."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "r2", "name": "R2", "type": "rgb", "command_topic": "L/21/C", "address": 21})
    await hass.services.async_call("light", SERVICE_TURN_ON, {"entity_id": "light.r2", ATTR_RGB_COLOR: (255, 0, 0)}, blocking=True)
    sent = get_sent_payload(mqtt_mock, "L/21/C")
    assert sent["type"] == "rgb"
    assert sent["r"] == 255
    assert "state" not in sent


async def test_light_turn_off(hass, mqtt_mock, setup_integration):
    """Test turn off."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "o1", "name": "O1", "command_topic": "L/50/C", "address": 50})
    await hass.services.async_call("light", SERVICE_TURN_OFF, {"entity_id": "light.o1"}, blocking=True)
    sent = get_sent_payload(mqtt_mock, "L/50/C")
    assert sent["dimming"] == 0
    assert "state" not in sent


async def test_light_default_type_discovery(hass, mqtt_mock, setup_integration):
    """Test onoff mode."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "def1", "name": "Def1", "type": "onoff", "address": 60})
    assert hass.states.get("light.def1").attributes.get("supported_color_modes") == [ColorMode.ONOFF]


async def test_light_cct_status_update(hass, mqtt_mock, setup_integration):
    """Test CCT status."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "cs1", "name": "CS1", "type": "cct", "address": 12})
    async_fire_mqtt_message(hass, "LYT/homeassistant/12/status", json.dumps({"address": 12, "type": "cct", "cct": {"dimming": 100, "kelvin": 4000}}))
    await hass.async_block_till_done()
    assert hass.states.get("light.cs1").attributes[ATTR_COLOR_TEMP_KELVIN] == 4000


async def test_light_rgb_status_update(hass, mqtt_mock, setup_integration):
    """Test RGB status."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "rs1", "name": "RS1", "type": "rgb", "address": 22})
    async_fire_mqtt_message(hass, "LYT/homeassistant/22/status", json.dumps({"address": 22, "type": "rgb", "rgb": {"r": 0, "g": 255, "b": 0}}))
    await hass.async_block_till_done()
    assert hass.states.get("light.rs1").attributes[ATTR_RGB_COLOR] == (0, 255, 0)


async def test_light_off_extended(hass, mqtt_mock, setup_integration):
    """Test off for CCT/RGB."""
    for t in ["cct", "rgb"]:
        await async_discover_light(hass, mqtt_mock, {"unique_id": f"{t}_off", "name": t, "type": t, "command_topic": f"L/{t}/C", "address": 100})
        await hass.services.async_call("light", SERVICE_TURN_OFF, {"entity_id": f"light.{t}_off"}, blocking=True)
    assert mqtt_mock.async_publish.called


async def test_light_status_extended(hass, mqtt_mock, setup_integration):
    """Test status branches."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "stat1", "name": "Stat1", "type": "cct", "address": 44})
    async_fire_mqtt_message(hass, "LYT/homeassistant/44/status", '{"address": 44, "type": "cct", "cct": {"color_temperature": 50, "dimming": 80}}')
    await hass.async_block_till_done()
    assert ATTR_COLOR_TEMP_KELVIN in hass.states.get("light.stat1").attributes

    await async_discover_light(hass, mqtt_mock, {"unique_id": "stat2", "name": "Stat2", "type": "rgb", "address": 33})
    async_fire_mqtt_message(hass, "LYT/homeassistant/33/status", '{"address": 33, "type": "rgb", "rgb": {"r": 255, "g": 10, "b": 20}}')
    await hass.async_block_till_done()
    assert hass.states.get("light.stat2").attributes[ATTR_RGB_COLOR] == (255, 10, 20)


async def test_light_coverage_extra(hass, mqtt_mock, setup_integration):
    """Extra coverage paths."""
    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex1", "name": "Ex1", "address": 88})
    async_fire_mqtt_message(hass, "LYT/homeassistant/88/status", "invalid")
    await hass.async_block_till_done()

    from lytiva import mireds_to_kelvin, kelvin_to_mireds
    assert mireds_to_kelvin(0) == 2700
    assert kelvin_to_mireds(0) == 370
    assert mireds_to_kelvin(None) == 2700
    assert kelvin_to_mireds(None) == 370
    assert mireds_to_kelvin("bad") == 2700
    assert kelvin_to_mireds("bad") == 370

    with patch("homeassistant.components.mqtt.async_publish", side_effect=Exception):
        await async_discover_light(hass, mqtt_mock, {"unique_id": "pub_err", "name": "PubErr", "address": 101, "command_topic": "L/101/C"})
        await hass.services.async_call("light", SERVICE_TURN_ON, {"entity_id": "light.puberr"}, blocking=True)
    
    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex2", "name": "Ex2", "address": 89})
    await hass.services.async_call("light", SERVICE_TURN_ON, {"entity_id": "light.ex2"}, blocking=True)

    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex3", "name": "Ex3", "address": "A1", "command_topic": "L/A1/C"})
    assert hass.states.get("light.ex3")

    # Address mismatch coverage
    async_fire_mqtt_message(hass, "LYT/homeassistant/A1/status", '{"address": "A2", "type": "dimmer", "dimming": 50}')
    await hass.async_block_till_done()

    with patch("homeassistant.helpers.entity.Entity.async_write_ha_state", side_effect=Exception):
         async_fire_mqtt_message(hass, "LYT/homeassistant/A1/status", '{"address": "A1", "type": "dimmer", "dimmer": {"dimming": 50}}')
         await hass.async_block_till_done()

    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex4", "name": "Ex4", "address": 90, "device": {"name": "D"}})
    assert dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "ex4")})

    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex5", "name": "Ex5", "address": 91})
    assert hass.states.get("light.ex5")

    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex6", "name": "Ex6", "address": 92})
    assert hass.states.get("light.ex6").attributes.get("supported_color_modes") == [ColorMode.BRIGHTNESS]

    # Implicit ON coverage
    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex7", "name": "Ex7", "type": "rgb", "address": 93})
    async_fire_mqtt_message(hass, "LYT/homeassistant/93/status", '{"address": 93, "type": "rgb", "rgb": {"r": 255, "g": 0, "b": 0}}')
    await hass.async_block_till_done()
    assert hass.states.get("light.ex7").state == STATE_ON

    # Dimmer implicit ON coverage
    await async_discover_light(hass, mqtt_mock, {"unique_id": "ex8", "name": "Ex8", "type": "dimmer", "address": 94})
    async_fire_mqtt_message(hass, "LYT/homeassistant/94/status", '{"address": 94, "type": "dimmer", "dimming": 50}')
    await hass.async_block_till_done()
    assert hass.states.get("light.ex8").state == STATE_ON

    # Nested payload coverage
    async_fire_mqtt_message(hass, "LYT/homeassistant/94/status", '{"address": 94, "type": "dimmer", "dimmer": {"dimming": 80}}')
    await hass.async_block_till_done()
    assert hass.states.get("light.ex8").attributes[ATTR_BRIGHTNESS] == round(80 * 255 / 100)
