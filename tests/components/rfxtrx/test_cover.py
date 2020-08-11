"""The tests for the Rfxtrx cover platform."""
from unittest.mock import call

import pytest

from homeassistant.core import State
from homeassistant.setup import async_setup_component

from tests.common import mock_restore_cache


async def test_one_cover(hass, rfxtrx):
    """Test with 1 cover."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {"rfxtrx": {"device": "abcd", "devices": {"0b1400cd0213c7f20d010f51": {}}}},
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.lightwaverf_siemens_0213c7_242")
    assert state

    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.lightwaverf_siemens_0213c7_242"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.lightwaverf_siemens_0213c7_242"},
        blocking=True,
    )

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.lightwaverf_siemens_0213c7_242"},
        blocking=True,
    )

    assert rfxtrx.transport.send.mock_calls == [
        call(bytearray(b"\n\x14\x00\x00\x02\x13\xc7\xf2\x0f\x00\x00")),
        call(bytearray(b"\n\x14\x00\x00\x02\x13\xc7\xf2\r\x00\x00")),
        call(bytearray(b"\n\x14\x00\x00\x02\x13\xc7\xf2\x0e\x00\x00")),
    ]


@pytest.mark.parametrize("state", ["open", "closed"])
async def test_state_restore(hass, rfxtrx, state):
    """State restoration."""

    entity_id = "cover.lightwaverf_siemens_0213c7_242"

    mock_restore_cache(hass, [State(entity_id, state)])

    assert await async_setup_component(
        hass,
        "rfxtrx",
        {"rfxtrx": {"device": "abcd", "devices": {"0b1400cd0213c7f20d010f51": {}}}},
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == state


async def test_several_covers(hass, rfxtrx):
    """Test with 3 covers."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "devices": {
                    "0b1400cd0213c7f20d010f51": {},
                    "0A1400ADF394AB010D0060": {},
                    "09190000009ba8010100": {},
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.lightwaverf_siemens_0213c7_242")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "LightwaveRF, Siemens 0213c7:242"

    state = hass.states.get("cover.lightwaverf_siemens_f394ab_1")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "LightwaveRF, Siemens f394ab:1"

    state = hass.states.get("cover.rollertrol_009ba8_1")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "RollerTrol 009ba8:1"


async def test_discover_covers(hass, rfxtrx_automatic):
    """Test with discovery of covers."""
    rfxtrx = rfxtrx_automatic

    await rfxtrx.signal("0a140002f38cae010f0070")
    state = hass.states.get("cover.lightwaverf_siemens_f38cae_1")
    assert state
    assert state.state == "open"

    await rfxtrx.signal("0a1400adf394ab020e0060")
    state = hass.states.get("cover.lightwaverf_siemens_f394ab_2")
    assert state
    assert state.state == "open"
