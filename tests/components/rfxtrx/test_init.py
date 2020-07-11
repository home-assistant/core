"""The tests for the Rfxtrx component."""
# pylint: disable=protected-access
import asyncio

from async_timeout import timeout

from homeassistant.components import rfxtrx
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

from . import _signal_event

from tests.common import assert_setup_component


async def test_default_config(hass):
    """Test configuration."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "/dev/serial/by-id/usb"
                + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                "dummy": True,
            }
        },
    )

    with assert_setup_component(1, "sensor"):
        await async_setup_component(
            hass,
            "sensor",
            {"sensor": {"platform": "rfxtrx", "automatic_add": True, "devices": {}}},
        )

    # Dummy startup is slow
    async with timeout(10):
        while len(hass.data[rfxtrx.DATA_RFXOBJECT].sensors()) < 2:
            await asyncio.sleep(0.1)

    assert len(hass.data[rfxtrx.DATA_RFXOBJECT].sensors()) == 2


async def test_valid_config(hass):
    """Test configuration."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "/dev/serial/by-id/usb"
                + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                "dummy": True,
            }
        },
    )


async def test_valid_config2(hass):
    """Test configuration."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "/dev/serial/by-id/usb"
                + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                "dummy": True,
                "debug": True,
            }
        },
    )


async def test_invalid_config(hass):
    """Test configuration."""
    assert not await async_setup_component(hass, "rfxtrx", {"rfxtrx": {}})

    assert not await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "/dev/serial/by-id/usb"
                + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                "invalid_key": True,
            }
        },
    )


async def test_fire_event(hass):
    """Test fire event."""
    assert await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "/dev/serial/by-id/usb"
                + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                "dummy": True,
            }
        },
    )

    assert await async_setup_component(
        hass,
        "switch",
        {
            "switch": {
                "platform": "rfxtrx",
                "automatic_add": True,
                "devices": {
                    "0b1100cd0213c7f210010f51": {
                        "name": "Test",
                        rfxtrx.ATTR_FIRE_EVENT: True,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    calls = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        calls.append(event)

    hass.bus.async_listen(rfxtrx.EVENT_BUTTON_PRESSED, record_event)

    state = hass.states.get("switch.test")
    assert state
    assert state.state == "off"

    await _signal_event(hass, "0b1100cd0213c7f210010f51")

    state = hass.states.get("switch.test")
    assert state
    assert state.state == "on"

    assert len(calls) == 1
    assert calls[0].data == {"entity_id": "switch.test", "state": "on"}


async def test_fire_event_sensor(hass):
    """Test fire event."""
    await async_setup_component(
        hass,
        "rfxtrx",
        {
            "rfxtrx": {
                "device": "/dev/serial/by-id/usb"
                + "-RFXCOM_RFXtrx433_A1Y0NJGR-if00-port0",
                "dummy": True,
            }
        },
    )

    await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": {
                "platform": "rfxtrx",
                "automatic_add": True,
                "devices": {
                    "0a520802060100ff0e0269": {
                        "name": "Test",
                        rfxtrx.ATTR_FIRE_EVENT: True,
                    }
                },
            }
        },
    )
    await hass.async_block_till_done()

    calls = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        calls.append(event)

    hass.bus.async_listen("signal_received", record_event)

    await _signal_event(hass, "0a520802060101ff0f0269")
    assert len(calls) == 5
    assert any(call.data == {"entity_id": "sensor.test_temperature"} for call in calls)
