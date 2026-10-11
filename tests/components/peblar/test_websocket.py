"""Tests for the Peblar event stream."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from peblar import PeblarConnectionError, PeblarSessionStatus, SessionState
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.SENSOR], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_the_stream_is_subscribed_to(mock_peblar: MagicMock) -> None:
    """Test the charger's session is followed as soon as the entry loads."""
    websocket = mock_peblar.websocket.return_value
    websocket.connect.assert_awaited_once()
    websocket.subscribe_session_status.assert_awaited_once()


def _async_report(mock_peblar: MagicMock, state: SessionState) -> None:
    """Have the charger report a session state on the stream."""
    websocket = mock_peblar.websocket.return_value
    handle_session_status = websocket.subscribe_session_status.call_args.args[0]
    handle_session_status(PeblarSessionStatus(state=state, meter_data=None))


async def test_a_session_change_pulls_the_polls_forward(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test an event asks the polls to catch up rather than waiting them out."""
    meter = mock_peblar.rest_api.return_value.meter
    meter.reset_mock()
    mock_peblar.meter_history.reset_mock()

    _async_report(mock_peblar, SessionState.CHARGING)
    await hass.async_block_till_done()

    meter.assert_awaited()
    mock_peblar.meter_history.assert_awaited()


async def test_a_session_saying_the_same_thing_is_let_be(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charger repeating itself does not set the polls off again.

    While a car charges the status arrives every couple of seconds and
    says the same thing every time. Acting on each one would have the
    meter history, a request many times heavier than the poll beside it,
    fetched around the clock for as long as the car is plugged in.

    The repeats are spread out here on purpose. Sent back to back the
    coordinator's own debouncer would swallow them, and this would pass
    whether or not anything looked at the state.
    """
    _async_report(mock_peblar, SessionState.CHARGING)
    await hass.async_block_till_done()

    mock_peblar.meter_history.reset_mock()

    for _ in range(3):
        freezer.tick(timedelta(seconds=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        _async_report(mock_peblar, SessionState.CHARGING)
        await hass.async_block_till_done()

    mock_peblar.meter_history.assert_not_awaited()


async def test_the_wait_backs_off_and_settles_once_the_charger_answers(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test how long the stream waits between attempts.

    A charger that cannot be reached is given more room each time. Once it
    answers, that is settled: a drop hours later starts over from the
    shortest wait rather than the longest one reached at startup.
    """
    websocket = mock_peblar.websocket.return_value
    websocket.connect.side_effect = [
        PeblarConnectionError("Gone"),
        PeblarConnectionError("Still gone"),
        None,
        None,
    ]

    hang_ups = 0

    async def _hang_up_once() -> None:
        nonlocal hang_ups
        hang_ups += 1
        if hang_ups == 1:
            return
        await asyncio.Event().wait()

    websocket.listen.side_effect = _hang_up_once

    waits: list[float] = []

    async def _record(delay: float) -> None:
        waits.append(delay)

    with patch("homeassistant.components.peblar.websocket.asyncio.sleep", _record):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Five seconds, then ten while the charger stays away. It answers on
    # the third try and hangs up, and the wait is back to five.
    assert waits[:3] == [5, 10, 5]


async def test_a_subscription_that_never_lands_keeps_backing_off(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test taking the socket is not the same as having a stream.

    A charger that accepts the connection but never completes the
    subscription would otherwise be retried every five seconds forever.
    """
    websocket = mock_peblar.websocket.return_value
    subscriptions = 0

    async def _refuse_twice(_callback: object) -> None:
        nonlocal subscriptions
        subscriptions += 1
        if subscriptions <= 2:
            raise PeblarConnectionError("Not listening")

    websocket.subscribe_session_status.side_effect = _refuse_twice

    waits: list[float] = []

    async def _record(delay: float) -> None:
        waits.append(delay)

    with patch("homeassistant.components.peblar.websocket.asyncio.sleep", _record):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # The socket opened every time, so a reset on that alone would have
    # left both waits at five seconds.
    assert waits[:2] == [5, 10]


async def test_the_stream_is_closed_when_the_entry_unloads(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the charger is let go of when the entry goes away."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_peblar.websocket.return_value.disconnect.assert_awaited()
