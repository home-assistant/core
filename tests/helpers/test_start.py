"""Test starting HA helpers."""
from homeassistant import core
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.helpers import start


async def test_at_start_when_running(hass):
    """Test at start when already running."""
    assert hass.is_running

    calls = []

    async def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_at_start_when_starting(hass):
    """Test at start when yet to start."""
    hass.state = core.CoreState.not_running
    assert not hass.is_running

    calls = []

    async def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 1
