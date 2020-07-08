"""The tests for the Rfxtrx light platform."""
from unittest.mock import call

import pytest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.setup import async_setup_component

from . import _signal_event

from tests.common import assert_setup_component


async def test_valid_config(hass, rfxtrx):
    """Test configuration."""
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            "light",
            {
                "light": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIRE_EVENT: True,
                        }
                    },
                }
            },
        )

        assert await async_setup_component(
            hass,
            "light",
            {
                "light": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            "signal_repetitions": 3,
                        }
                    },
                }
            },
        )


async def test_default_config(hass, rfxtrx):
    """Test with 0 switches."""
    with assert_setup_component(1):
        await async_setup_component(
            hass, "light", {"light": {"platform": "rfxtrx", "devices": {}}}
        )
        await hass.async_block_till_done()

    assert 0 == len(rfxtrx_core.RFX_DEVICES)


async def test_one_light(hass, rfxtrx):
    """Test with 1 light."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "rfxtrx",
                "devices": {"0b1100cd0213c7f210010f51": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.test"}, blocking=True
    )
    state = hass.states.get("light.test")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.test"}, blocking=True
    )
    state = hass.states.get("light.test")
    assert state.state == "off"
    assert state.attributes.get("brightness") is None

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", "brightness": 100},
        blocking=True,
    )
    state = hass.states.get("light.test")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 100

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.test", "brightness": 10}, blocking=True
    )
    state = hass.states.get("light.test")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 10

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.test", "brightness": 255},
        blocking=True,
    )
    state = hass.states.get("light.test")
    assert state.state == "on"
    assert state.attributes.get("brightness") == 255

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": "light.test"}, blocking=True
    )
    state = hass.states.get("light.test")
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


async def test_several_lights(hass, rfxtrx):
    """Test with 3 lights."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "rfxtrx",
                "signal_repetitions": 3,
                "devices": {
                    "0b1100cd0213c7f230010f71": {"name": "Test"},
                    "0b1100100118cdea02010f70": {"name": "Bath"},
                    "0b1100101118cdea02010f70": {"name": "Living"},
                },
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 3

    state = hass.states.get("light.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"

    state = hass.states.get("light.bath")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Bath"

    state = hass.states.get("light.living")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Living"

    assert len(hass.states.async_all()) == 3


@pytest.mark.parametrize("repetitions", [1, 3])
async def test_repetitions(hass, rfxtrx, repetitions):
    """Test signal repetitions."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "rfxtrx",
                "signal_repetitions": repetitions,
                "devices": {"0b1100cd0213c7f230010f71": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.test"}, blocking=True
    )
    await hass.async_block_till_done()

    assert rfxtrx.transport.send.call_count == repetitions


async def test_discover_light(hass, rfxtrx):
    """Test with discovery of lights."""
    await async_setup_component(
        hass,
        "light",
        {"light": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0b11009e00e6116202020070")
    state = hass.states.get("light.0b11009e00e6116202020070")
    assert state
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "0b11009e00e6116202020070"

    await _signal_event(hass, "0b1100120118cdea02020070")
    state = hass.states.get("light.0b1100120118cdea02020070")
    assert state
    assert state.state == "on"
    assert state.attributes.get("friendly_name") == "0b1100120118cdea02020070"


async def test_discover_light_noautoadd(hass, rfxtrx):
    """Test with discover of light when auto add is False."""
    await async_setup_component(
        hass,
        "light",
        {"light": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0b1100120118cdea02020070")
    assert hass.states.async_all() == []

    await _signal_event(hass, "0b1100120118cdea02010070")
    assert hass.states.async_all() == []

    await _signal_event(hass, "0b1100120118cdea02020070")
    assert hass.states.async_all() == []
