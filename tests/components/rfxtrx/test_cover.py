"""The tests for the Rfxtrx cover platform."""
import RFXtrx as rfxtrxmod

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

    assert 0 == len(rfxtrx_core.RFX_DEVICES)


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

    hass.data[rfxtrx_core.DATA_RFXOBJECT] = rfxtrxmod.Core(
        "", transport_protocol=rfxtrxmod.DummyTransport
    )

    assert 1 == len(rfxtrx_core.RFX_DEVICES)
    for id in rfxtrx_core.RFX_DEVICES:
        entity = rfxtrx_core.RFX_DEVICES[id]
        entity.hass = hass
        assert entity.signal_repetitions == 1
        assert not entity.should_fire_event
        assert not entity.should_poll
        entity.open_cover()
        entity.close_cover()
        entity.stop_cover()


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

    assert 3 == len(rfxtrx_core.RFX_DEVICES)
    device_num = 0
    for id in rfxtrx_core.RFX_DEVICES:
        entity = rfxtrx_core.RFX_DEVICES[id]
        assert entity.signal_repetitions == 3
        if entity.name == "Living":
            device_num = device_num + 1
        elif entity.name == "Bath":
            device_num = device_num + 1
        elif entity.name == "Test":
            device_num = device_num + 1

    assert 3 == device_num


async def test_discover_covers(hass, rfxtrx):
    """Test with discovery of covers."""
    assert await async_setup_component(
        hass,
        "cover",
        {"cover": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
    )
    await hass.async_block_till_done()

    event = rfxtrx_core.get_rfx_object("0a140002f38cae010f0070")
    event.data = bytearray(
        [0x0A, 0x14, 0x00, 0x02, 0xF3, 0x8C, 0xAE, 0x01, 0x0F, 0x00, 0x70]
    )

    await _signal_event(hass, event)
    assert 1 == len(rfxtrx_core.RFX_DEVICES)

    event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
    event.data = bytearray(
        [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
    )

    await _signal_event(hass, event)
    assert 2 == len(rfxtrx_core.RFX_DEVICES)

    # Trying to add a sensor
    event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
    event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
    await _signal_event(hass, event)
    assert 2 == len(rfxtrx_core.RFX_DEVICES)

    # Trying to add a light
    event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
    event.data = bytearray(
        [0x0B, 0x11, 0x11, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x02, 0x0F, 0x70]
    )
    await _signal_event(hass, event)
    assert 2 == len(rfxtrx_core.RFX_DEVICES)


async def test_discover_cover_noautoadd(hass, rfxtrx):
    """Test with discovery of cover when auto add is False."""
    assert await async_setup_component(
        hass,
        "cover",
        {"cover": {"platform": "rfxtrx", "automatic_add": False, "devices": {}}},
    )
    await hass.async_block_till_done()

    event = rfxtrx_core.get_rfx_object("0a1400adf394ab010d0060")
    event.data = bytearray(
        [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x01, 0x0D, 0x00, 0x60]
    )

    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)

    event = rfxtrx_core.get_rfx_object("0a1400adf394ab020e0060")
    event.data = bytearray(
        [0x0A, 0x14, 0x00, 0xAD, 0xF3, 0x94, 0xAB, 0x02, 0x0E, 0x00, 0x60]
    )
    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)

    # Trying to add a sensor
    event = rfxtrx_core.get_rfx_object("0a52085e070100b31b0279")
    event.data = bytearray(b"\nR\x08^\x07\x01\x00\xb3\x1b\x02y")
    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)

    # Trying to add a light
    event = rfxtrx_core.get_rfx_object("0b1100100118cdea02010f70")
    event.data = bytearray(
        [0x0B, 0x11, 0x11, 0x10, 0x01, 0x18, 0xCD, 0xEA, 0x01, 0x02, 0x0F, 0x70]
    )
    await _signal_event(hass, event)
    assert 0 == len(rfxtrx_core.RFX_DEVICES)
