"""The tests for the Rfxtrx light platform."""
from unittest.mock import call

import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.core import State
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


async def test_one_light(hass, rfxtrx):
    """Test with 1 light."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {"rfxtrx": {"device": "abcd", "devices": {"0b1100cd0213c7f210020f51": {}}}},
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.ac_213c7f2_16")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:16"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.ac_213c7f2_16"}, blocking=True
    )
    state = hass.states.get("light.ac_213c7f2_16")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.ac_213c7f2_16"}, blocking=True
    )
    state = hass.states.get("light.ac_213c7f2_16")
    assert state.state == "off"
    assert state.attributes.get("brightness") is None

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.ac_213c7f2_16", "brightness": 100},
        blocking=True,
    )
    state = hass.states.get("light.ac_213c7f2_16")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 100

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.ac_213c7f2_16", "brightness": 10},
        blocking=True,
    )
    state = hass.states.get("light.ac_213c7f2_16")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 10

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.ac_213c7f2_16", "brightness": 255},
        blocking=True,
    )
    state = hass.states.get("light.ac_213c7f2_16")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.ac_213c7f2_16"}, blocking=True
    )
    state = hass.states.get("light.ac_213c7f2_16")
    assert state.state == "off"
    assert state.attributes.get("brightness") is None

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x01\x00\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x00\x00\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x02\x06\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x02\x00\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x02\x0f\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x00\x00\x00")),
    ]


@pytest.mark.parametrize("state,brightness", [["on", 100], ["on", 50], ["off", None]])
async def test_state_restore(hass, rfxtrx, state, brightness):
    """State restoration."""

    entity_id = "light.ac_213c7f2_16"

    mock_restore_cache(
        hass, [State(entity_id, state, attributes={ATTR_BRIGHTNESS: brightness})]
    )

    assert await async_setup_component(
        hass,
        "rfxtrx",
        {"rfxtrx": {"device": "abcd", "devices": {"0b1100cd0213c7f210020f51": {}}}},
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state
    assert hass.states.get(entity_id).attributes.get(ATTR_BRIGHTNESS) == brightness


async def test_several_lights(hass, rfxtrx):
    """Test with 3 lights."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "devices": {
                    "0b1100cd0213c7f230020f71": {},
                    "0b1100100118cdea02020f70": {},
                    "0b1100101118cdea02050f70": {},
                },
            }
        },
    )
    await hass.async_block_till_done()
    await hass.async_start()

    state = hass.states.get("light.ac_213c7f2_48")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    state = hass.states.get("light.ac_118cdea_2")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"

    state = hass.states.get("light.ac_1118cdea_2")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 1118cdea:2"

    await rfxtrx.signal("0b1100cd0213c7f230010f71")
    state = hass.states.get("light.ac_213c7f2_48")
    assert state
    assert state.state == "on"

    await rfxtrx.signal("0b1100cd0213c7f230000f71")
    state = hass.states.get("light.ac_213c7f2_48")
    assert state
    assert state.state == "off"

    await rfxtrx.signal("0b1100cd0213c7f230020f71")
    state = hass.states.get("light.ac_213c7f2_48")
    assert state
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255


@pytest.mark.parametrize("repetitions", [1, 3])
async def test_repetitions(hass, rfxtrx, repetitions):
    """Test signal repetitions."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "devices": {
                    "0b1100cd0213c7f230020f71": {"signal_repetitions": repetitions}
                },
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.ac_213c7f2_48"}, blocking=True
    )
    await hass.async_block_till_done()

    assert rfxtrx.transport.send.call_count == repetitions


async def test_discover_light(hass, rfxtrx_automatic):
    """Test with discovery of lights."""
    rfxtrx = rfxtrx_automatic

    await rfxtrx.signal("0b11009e00e6116202020070")
    state = hass.states.get("light.ac_0e61162_2")
    assert state
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "AC 0e61162:2"

    await rfxtrx.signal("0b1100120118cdea02020070")
    state = hass.states.get("light.ac_118cdea_2")
    assert state
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"
