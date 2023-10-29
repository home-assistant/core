"""Provide tests for mysensors light platform."""
from __future__ import annotations

from collections.abc import Callable
from unittest.mock import MagicMock, call

from mysensors.sensor import Sensor

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_BATTERY_LEVEL
from homeassistant.core import HomeAssistant


async def test_dimmer_node(
    hass: HomeAssistant,
    dimmer_node: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a dimmer node."""
    entity_id = "light.dimmer_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    # Test turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;1\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;100\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 255

    transport_write.reset_mock()

    # Test turn on brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, "brightness": 128},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;3;50\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;50\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 128

    transport_write.reset_mock()

    # Test turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;0\n")

    receive_message("1;1;1;0;2;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"


async def test_rgb_node(
    hass: HomeAssistant,
    rgb_node: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a rgb node."""
    entity_id = "light.rgb_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    # Test turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;1\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;100\n")
    receive_message("1;1;1;0;40;ffffff\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_RGB_COLOR] == (255, 255, 255)

    transport_write.reset_mock()

    # Test turn on brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, "brightness": 128},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;3;50\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;50\n")
    receive_message("1;1;1;0;40;ffffff\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (255, 255, 255)

    transport_write.reset_mock()

    # Test turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;0\n")

    receive_message("1;1;1;0;2;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"

    transport_write.reset_mock()

    # Test turn on rgb
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, ATTR_RGB_COLOR: (255, 0, 0)},
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list[0] == call("1;1;1;1;2;1\n")
    assert transport_write.call_args_list[1] == call("1;1;1;1;40;ff0000\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;50\n")
    receive_message("1;1;1;0;40;ff0000\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGB_COLOR] == (255, 0, 0)


async def test_rgbw_node(
    hass: HomeAssistant,
    rgbw_node: Sensor,
    receive_message: Callable[[str], None],
    transport_write: MagicMock,
) -> None:
    """Test a rgbw node."""
    entity_id = "light.rgbw_node_1_1"

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"
    assert state.attributes[ATTR_BATTERY_LEVEL] == 0

    # Test turn on
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;1\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;100\n")
    receive_message("1;1;1;0;41;ffffffff\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 255
    assert state.attributes[ATTR_RGBW_COLOR] == (255, 255, 255, 255)

    transport_write.reset_mock()

    # Test turn on brightness
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, "brightness": 128},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;3;50\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;50\n")
    receive_message("1;1;1;0;41;ffffffff\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGBW_COLOR] == (255, 255, 255, 255)

    transport_write.reset_mock()

    # Test turn off
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )

    assert transport_write.call_count == 1
    assert transport_write.call_args == call("1;1;1;1;2;0\n")

    receive_message("1;1;1;0;2;0\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "off"

    transport_write.reset_mock()

    # Test turn on rgbw
    await hass.services.async_call(
        LIGHT_DOMAIN,
        "turn_on",
        {"entity_id": entity_id, ATTR_RGBW_COLOR: (255, 0, 0, 0)},
        blocking=True,
    )

    assert transport_write.call_count == 2
    assert transport_write.call_args_list[0] == call("1;1;1;1;2;1\n")
    assert transport_write.call_args_list[1] == call("1;1;1;1;41;ff000000\n")

    receive_message("1;1;1;0;2;1\n")
    receive_message("1;1;1;0;3;50\n")
    receive_message("1;1;1;0;41;ff000000\n")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state
    assert state.state == "on"
    assert state.attributes[ATTR_BRIGHTNESS] == 128
    assert state.attributes[ATTR_RGBW_COLOR] == (255, 0, 0, 0)
