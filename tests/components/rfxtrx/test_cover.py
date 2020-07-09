"""The tests for the Rfxtrx cover platform."""
from unittest.mock import call

from homeassistant.components import rfxtrx as rfxtrx_core
from homeassistant.setup import async_setup_component

from . import _signal_event

from tests.common import assert_setup_component


async def test_valid_config(hass, rfxtrx):
    """Test configuration."""
    with assert_setup_component(1):
        assert await async_setup_component(
            hass,
            "cover",
            {
                "cover": {
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


async def test_default_config(hass, rfxtrx):
    """Test with 0 cover."""
    assert await async_setup_component(
        hass, "cover", {"cover": {"platform": "rfxtrx", "devices": {}}}
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0


async def test_one_cover(hass, rfxtrx):
    """Test with 1 cover."""
    assert await async_setup_component(
        hass,
        "cover",
        {
            "cover": {
                "platform": "rfxtrx",
                "devices": {"0b1400cd0213c7f210010f51": {"name": "Test"}},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    await hass.services.async_call(
        "cover", "open_cover", {"entity_id": "cover.test"}, blocking=True
    )

    await hass.services.async_call(
        "cover", "close_cover", {"entity_id": "cover.test"}, blocking=True
    )

    await hass.services.async_call(
        "cover", "stop_cover", {"entity_id": "cover.test"}, blocking=True
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
        "cover",
        {
            "cover": {
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

    state = hass.states.get("cover.test")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "Test"

    state = hass.states.get("cover.bath")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "Bath"

    state = hass.states.get("cover.living")
    assert state
    assert state.state == "closed"
    assert state.attributes.get("friendly_name") == "Living"

    assert len(hass.states.async_all()) == 3


async def test_discover_covers(hass, rfxtrx):
    """Test with discovery of covers."""
    assert await async_setup_component(
        hass,
        "cover",
        {"cover": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0a140002f38cae010f0070")
    assert len(hass.states.async_all()) == 1

    await _signal_event(hass, "0a1400adf394ab020e0060")
    assert len(hass.states.async_all()) == 2

    # Trying to add a sensor
    await _signal_event(hass, "0a52085e070100b31b0279")
    assert len(hass.states.async_all()) == 2

    # Trying to add a light
    await _signal_event(hass, "0b1100100118cdea02010f70")
    assert len(hass.states.async_all()) == 2


async def test_discover_cover_noautoadd(hass, rfxtrx):
    """Test with discovery of cover when auto add is False."""
    assert await async_setup_component(
        hass,
        "cover",
        {"cover": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
    )
    await hass.async_block_till_done()

    await _signal_event(hass, "0a1400adf394ab010d0060")
    assert len(hass.states.async_all()) == 0

    await _signal_event(hass, "0a1400adf394ab020e0060")
    assert len(hass.states.async_all()) == 0
