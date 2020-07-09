"""The tests for the RFXtrx switch platform."""
from unittest.mock import call

import pytest

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.setup import async_setup_component

from . import _signal_event

from tests.common import assert_setup_component


async def test_valid_config(hass, rfxtrx):
    """Test configuration."""
    with assert_setup_component(1):
        await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
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
        await hass.async_block_till_done()


async def test_valid_config_int_device_id(hass, rfxtrx):
    """Test configuration."""
    with assert_setup_component(1):
        await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "devices": {
                        710000141010170: {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIRE_EVENT: True,
                        }
                    },
                }
            },
        )
        await hass.async_block_till_done()


async def test_invalid_config2(hass, rfxtrx):
    """Test invalid configuration."""
    with assert_setup_component(0):
        await async_setup_component(
            hass,
            "switch",
            {
                "switch": {
                    "platform": "rfxtrx",
                    "automatic_add": True,
                    "invalid_key": "afda",
                    "devices": {
                        "0b1100cd0213c7f210010f51": {
                            "name": "Test",
                            rfxtrx_core.ATTR_FIRE_EVENT: True,
                        }
                    },
                }
            },
        )
        await hass.async_block_till_done()


async def test_default_config(hass, rfxtrx):
    """Test with 0 switches."""
    await async_setup_component(
        hass, "switch", {"switch": {"platform": "rfxtrx", "devices": {}}}
    )
    await hass.async_block_till_done()
    assert hass.states.async_all() == []


async def test_one_switch(hass, rfxtrx):
    """Test with 1 switch."""
    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "rfxtrx",
                "devices": {"0b1100cd0213c7f210010f51": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )

    state = hass.states.get("switch.test")
    assert state.state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.test"}, blocking=True
    )

    state = hass.states.get("switch.test")
    assert state.state == "off"

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x01\x00\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x00\x00\x00")),
    ]


async def test_several_switches(hass, rfxtrx):
    """Test with 3 switches."""
    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
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

    state = hass.states.get("switch.test")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Test"

    state = hass.states.get("switch.bath")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Bath"

    state = hass.states.get("switch.living")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "Living"


@pytest.mark.parametrize("repetitions", [1, 3])
async def test_repetitions(hass, rfxtrx, repetitions):
    """Test signal repetitions."""
    await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "rfxtrx",
                "signal_repetitions": repetitions,
                "devices": {"0b1100cd0213c7f230010f71": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.test"}, blocking=True
    )
    await hass.async_block_till_done()

    assert rfxtrx.transport.send.call_count == repetitions


async def test_discover_switch(hass, rfxtrx):
    """Test with discovery of switches."""
    await async_setup_component(
        hass,
        "switch",
        {"switch": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("switch.0b1100100118cdea02010f70")
    assert state
    assert state.state == "on"

    await _signal_event(hass, "0b1100100118cdeb02010f70")
    state = hass.states.get("switch.0b1100100118cdeb02010f70")
    assert state
    assert state.state == "on"

    # Trying to add a sensor
    await _signal_event(hass, "0a52085e070100b31b0279")
    state = hass.states.get("sensor.0a52085e070100b31b0279")
    assert state is None

    # Trying to add a light
    await _signal_event(hass, "0b1100100118cdea02010f70")
    state = hass.states.get("light.0b1100100118cdea02010f70")
    assert state is None

    # Trying to add a rollershutter
    await _signal_event(hass, "0a1400adf394ab020e0060")
    state = hass.states.get("cover.0a1400adf394ab020e0060")
    assert state is None


async def test_discover_switch_noautoadd(hass, rfxtrx):
    """Test with discovery of switch when auto add is False."""
    await async_setup_component(
        hass,
        "switch",
        {"switch": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
    )
    await hass.async_block_till_done()

    # Trying to add switch
    await _signal_event(hass, "0b1100100118cdea02010f70")
    assert hass.states.async_all() == []
