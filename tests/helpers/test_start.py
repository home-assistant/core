"""Test starting HA helpers."""
from homeassistant import core
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.helpers import start


async def test_at_start_when_running_awaitable(hass):
    """Test at start when already running."""
    assert hass.state == core.CoreState.running
    assert hass.is_running

    calls = []

    async def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.state = core.CoreState.starting
    assert hass.is_running

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_at_start_when_running_callback(hass, caplog):
    """Test at start when already running."""
    assert hass.state == core.CoreState.running
    assert hass.is_running

    calls = []

    @core.callback
    def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)()
    assert len(calls) == 1

    hass.state = core.CoreState.starting
    assert hass.is_running

    start.async_at_start(hass, cb_at_start)()
    assert len(calls) == 2

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_at_start_when_starting_awaitable(hass):
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


async def test_at_start_when_starting_callback(hass, caplog):
    """Test at start when yet to start."""
    hass.state = core.CoreState.not_running
    assert not hass.is_running

    calls = []

    @core.callback
    def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    cancel = start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 1

    cancel()

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_cancelling_when_running(hass, caplog):
    """Test cancelling at start when already running."""
    assert hass.state == core.CoreState.running
    assert hass.is_running

    calls = []

    async def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)()
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_cancelling_when_starting(hass):
    """Test cancelling at start when yet to start."""
    hass.state = core.CoreState.not_running
    assert not hass.is_running

    calls = []

    @core.callback
    def cb_at_start(hass):
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)()
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 0
