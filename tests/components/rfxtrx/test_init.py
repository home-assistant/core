"""The tests for the Rfxtrx component."""

from homeassistant.components import rfxtrx
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

from . import _signal_event


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
                "automatic_add": True,
                "devices": {"0b1100cd0213c7f210010f51": {rfxtrx.ATTR_FIRE_EVENT: True}},
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

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state
    assert state.state == "off"

    await _signal_event(hass, "0b1100cd0213c7f210010f51")

    state = hass.states.get("switch.ac_213c7f2_16")
    assert state
    assert state.state == "on"

    assert any(
        call.data == {"entity_id": "switch.ac_213c7f2_16", "state": "on"}
        for call in calls
    )


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
                "automatic_add": True,
                "devices": {"0a520802060100ff0e0269": {rfxtrx.ATTR_FIRE_EVENT: True}},
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
    assert any(
        call.data
        == {"entity_id": "sensor.wt260_wt260h_wt440h_wt450_wt450h_06_01_temperature"}
        for call in calls
    )
