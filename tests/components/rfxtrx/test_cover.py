"""The tests for the Rfxtrx cover platform."""
from unittest.mock import call

from homeassistant.setup import async_setup_component

from . import _signal_event


async def test_one_cover(hass, rfxtrx):
    """Test with 1 cover."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "covers": {"0b1400cd0213c7f210010f51": {}},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

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


async def test_several_covers(hass, rfxtrx):
    """Test with 3 covers."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "abcd",
                "dummy": True,
                "covers": {
                    "0b1100cd0213c7f230010f71": {},
                    "0b1100100118cdea02010f70": {},
                    "0b1100101118cdea02010f70": {},
                },
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("cover.ac_213c7f2_48")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "AC 213c7f2:48"

    state = hass.states.get("cover.ac_118cdea_2")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "AC 118cdea:2"

    state = hass.states.get("cover.ac_1118cdea_2")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "AC 1118cdea:2"

    assert len(hass.states.async_all()) == 3


async def test_discover_covers(hass, rfxtrx):
    """Test with discovery of covers."""
    assert await async_setup_component(
        hass, "rfxtrx", {"rfxtrx": {"device": "abcd", "dummy": True}}
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0a140002f38cae010f0070")
    state = hass.states.get("cover.lightwaverf_siemens_f38cae_1")
    assert state
    assert state.state == "open"

    await _signal_event(hass, "0a1400adf394ab020e0060")
    state = hass.states.get("cover.lightwaverf_siemens_f394ab_2")
    assert state
    assert state.state == "open"
