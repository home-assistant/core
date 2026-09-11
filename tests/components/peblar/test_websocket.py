"""Tests for the Peblar event stream."""

import asyncio
from unittest.mock import MagicMock, patch

from peblar import PeblarConnectionError, PeblarSessionStatus, SessionState
import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = [
    pytest.mark.parametrize("init_integration", [Platform.SENSOR], indirect=True),
    pytest.mark.usefixtures("init_integration"),
]


async def test_the_stream_is_subscribed_to(mock_peblar: MagicMock) -> None:
    """Test the charger's session is followed as soon as the entry loads."""
    websocket = mock_peblar.websocket.return_value
    websocket.connect.assert_awaited_once()
    websocket.subscribe_session_status.assert_awaited_once()


async def test_a_session_change_pulls_the_poll_forward(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test an event asks the poll to catch up rather than waiting it out."""
    meter = mock_peblar.rest_api.return_value.meter
    meter.reset_mock()

    websocket = mock_peblar.websocket.return_value
    handle_session_status = websocket.subscribe_session_status.call_args.args[0]
    handle_session_status(
        PeblarSessionStatus(state=SessionState.CHARGING, meter_data=None)
    )
    await hass.async_block_till_done()

    meter.assert_awaited()


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
