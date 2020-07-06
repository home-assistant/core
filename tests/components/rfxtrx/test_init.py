"""The tests for the Rfxtrx component."""
# pylint: disable=protected-access
import asyncio

from async_timeout import timeout

from homeassistant.components import rfxtrx
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

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
    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    calls = []

    @callback
    def record_event(event):
        """Add recorded event to set."""
        assert event.event_type == "rfxtrx_event"
        calls.append(event.data)

    hass.bus.async_listen(rfxtrx.const.EVENT_RFXTRX_EVENT, record_event)

    async def async_trigger_packet(packet):
        await hass.async_add_executor_job(
            hass.data[rfxtrx.DATA_RFXOBJECT].event_callback,
            rfxtrx.get_rfx_object(packet),
        )
        await hass.async_block_till_done()

    await async_trigger_packet("0b1100cd0213c7f210010f51")
    await async_trigger_packet("0716000100900970")

    assert calls == [
        {
            "packet_type": 17,
            "sub_type": 0,
            "type_string": "AC",
            "id_string": "213c7f2:16",
            "data": "0b1100cd0213c7f210010f51",
            "values": {"Command": "On", "Rssi numeric": 5},
        },
        {
            "packet_type": 22,
            "sub_type": 0,
            "type_string": "Byron SX",
            "id_string": "00:90",
            "data": "0716000100900970",
            "values": {"Sound": 9, "Battery numeric": 0, "Rssi numeric": 7},
        },
    ]
