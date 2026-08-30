"""Tests for the Peblar event stream."""

import asyncio
from datetime import timedelta
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


def _session_callback(mock_peblar: MagicMock):
    """Return the callback the listener subscribed with."""
    websocket = mock_peblar.websocket.return_value
    websocket.subscribe_session_status.assert_called_once()
    return websocket.subscribe_session_status.call_args.args[0]


async def test_the_stream_is_subscribed_to(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
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

    _session_callback(mock_peblar)(
        PeblarSessionStatus(state=SessionState.CHARGING, meter_data=None)
    )
    await hass.async_block_till_done()

    meter.assert_awaited()


async def test_the_stream_is_opened_again_after_it_falls_over(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a charger that drops off is picked back up.

    The stream only makes the poll quicker, so losing it is not fatal, but
    losing it for good would quietly undo the whole thing.
    """
    websocket = mock_peblar.websocket.return_value
    attempts = 0

    async def _fall_over_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PeblarConnectionError("Gone")
        await asyncio.Event().wait()

    websocket.listen.side_effect = _fall_over_once
    websocket.connect.reset_mock()

    with patch(
        "homeassistant.components.peblar.websocket.EVENT_STREAM_RETRY_MINIMUM",
        timedelta(0),
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert attempts > 1
    assert websocket.connect.await_count > 1


async def test_a_stream_the_charger_closes_is_opened_again(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a charger hanging up cleanly is not treated as a failure.

    Nothing went wrong, so there is no reason to start backing off.
    """
    websocket = mock_peblar.websocket.return_value
    attempts = 0

    async def _hang_up_once() -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return
        await asyncio.Event().wait()

    websocket.listen.side_effect = _hang_up_once
    websocket.connect.reset_mock()

    with patch(
        "homeassistant.components.peblar.websocket.EVENT_STREAM_RETRY_MINIMUM",
        timedelta(0),
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert attempts > 1
    assert websocket.connect.await_count > 1


async def test_the_stream_is_closed_when_the_entry_unloads(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the charger is let go of when the entry goes away."""
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_peblar.websocket.return_value.disconnect.assert_awaited()
