"""Test starting HA helpers."""

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, callback
from homeassistant.helpers import start


async def test_at_start_when_running_awaitable(hass: HomeAssistant) -> None:
    """Test at start when already running."""
    assert hass.state is CoreState.running
    assert hass.is_running

    calls = []

    async def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 1

    hass.set_state(CoreState.starting)
    assert hass.is_running

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_at_start_when_running_callback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test at start when already running."""
    assert hass.state is CoreState.running
    assert hass.is_running

    calls = []

    @callback
    def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)()
    assert len(calls) == 1

    hass.set_state(CoreState.starting)
    assert hass.is_running

    start.async_at_start(hass, cb_at_start)()
    assert len(calls) == 2

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_at_start_when_starting_awaitable(hass: HomeAssistant) -> None:
    """Test at start when yet to start."""
    hass.set_state(CoreState.not_running)
    assert not hass.is_running

    calls = []

    async def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_at_start_when_starting_callback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test at start when yet to start."""
    hass.set_state(CoreState.not_running)
    assert not hass.is_running

    calls = []

    @callback
    def cb_at_start(hass: HomeAssistant) -> None:
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


async def test_cancelling_at_start_when_running(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test cancelling at start when already running."""
    assert hass.state is CoreState.running
    assert hass.is_running

    calls = []

    async def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)()
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_cancelling_at_start_when_starting(hass: HomeAssistant) -> None:
    """Test cancelling at start when yet to start."""
    hass.set_state(CoreState.not_running)
    assert not hass.is_running

    calls = []

    @callback
    def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_start(hass, cb_at_start)()
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_at_started_when_running_awaitable(hass: HomeAssistant) -> None:
    """Test at started when already started."""
    assert hass.state is CoreState.running

    calls = []

    async def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_started(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Test the job is not run if state is CoreState.starting
    hass.set_state(CoreState.starting)

    start.async_at_started(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_at_started_when_running_callback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test at started when already running."""
    assert hass.state is CoreState.running

    calls = []

    @callback
    def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_started(hass, cb_at_start)()
    assert len(calls) == 1

    # Test the job is not run if state is CoreState.starting
    hass.set_state(CoreState.starting)

    start.async_at_started(hass, cb_at_start)()
    assert len(calls) == 1

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_at_started_when_starting_awaitable(hass: HomeAssistant) -> None:
    """Test at started when yet to start."""
    hass.set_state(CoreState.not_running)

    calls = []

    async def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_started(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_at_started_when_starting_callback(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test at started when yet to start."""
    hass.set_state(CoreState.not_running)

    calls = []

    @callback
    def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    cancel = start.async_at_started(hass, cb_at_start)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert len(calls) == 1

    cancel()

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_cancelling_at_started_when_running(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test cancelling at start when already running."""
    assert hass.state is CoreState.running
    assert hass.is_running

    calls = []

    async def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_started(hass, cb_at_start)()
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Check the unnecessary cancel did not generate warnings or errors
    for record in caplog.records:
        assert record.levelname in ("DEBUG", "INFO")


async def test_cancelling_at_started_when_starting(hass: HomeAssistant) -> None:
    """Test cancelling at start when yet to start."""
    hass.set_state(CoreState.not_running)
    assert not hass.is_running

    calls = []

    @callback
    def cb_at_start(hass: HomeAssistant) -> None:
        """Home Assistant is started."""
        calls.append(1)

    start.async_at_started(hass, cb_at_start)()
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    assert len(calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    assert len(calls) == 0
