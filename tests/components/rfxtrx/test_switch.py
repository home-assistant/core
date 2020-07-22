"""The tests for the RFXtrx switch platform."""
from unittest.mock import call

import pytest

from homeassistant.core import State
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


async def test_one_switch(hass, rfxtrx):
    """Test with 1 switch."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {"rfxtrx": {"device": "abcd", "devices": {"0b1100cd0213c7f210010f51": {}}}},
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:16"

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.ac_213c7f2_16"}, blocking=True
    )

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state.state == "on"

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": "switch.ac_213c7f2_16"}, blocking=True
    )

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state.state == "off"

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x01\x00\x00")),
        call(bytearray(b"\x0b\x11\x00\x00\x02\x13\xc7\xf2\x10\x00\x00\x00")),
    ]


@pytest.mark.parametrize("state", ["on", "off"])
async def test_state_restore(hass, rfxtrx, state):
    """State restoration."""

    entity_id = "switch.ac_213c7f2_16"

    mock_restore_cache(hass, [State(entity_id, state)])

    assert await async_setup_component(
        hass,
        "rfxtrx",
        {"rfxtrx": {"device": "abcd", "devices": {"0b1100cd0213c7f210010f51": {}}}},
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


async def test_several_switches(hass, rfxtrx):
    """Test with 3 switches."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "devices": {
                    "0b1100cd0213c7f230010f71": {},
                    "0b1100100118cdea02010f70": {},
                    "0b1100101118cdea02010f70": {},
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.ac_213c7f2_48")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    state = hass.states.get("switch.ac_118cdea_2")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"

    state = hass.states.get("switch.ac_1118cdea_2")
    assert state
    assert state.state == "off"
    assert state.attributes.get("friendly_name") == "AC 1118cdea:2"


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
                    "0b1100cd0213c7f230010f71": {"signal_repetitions": repetitions}
                },
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.ac_213c7f2_48"}, blocking=True
    )
    await hass.async_block_till_done()

    assert rfxtrx.transport.send.call_count == repetitions


async def test_discover_switch(hass, rfxtrx):
    """Test with discovery of switches."""
    assert await async_setup_component(
        hass, "rfxtrx", {"rfxtrx": {"device": "abcd", "automatic_add": True}},
    )
    await hass.async_block_till_done()
    await hass.async_start()

    await rfxtrx.signal("0b1100100118cdea02010f70")
    state = hass.states.get("switch.ac_118cdea_2")
    assert state
    assert state.state == "on"

    await rfxtrx.signal("0b1100100118cdeb02010f70")
    state = hass.states.get("switch.ac_118cdeb_2")
    assert state
    assert state.state == "on"
