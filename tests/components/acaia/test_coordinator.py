"""Tests for the acaia coordinator connection handling."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source,
)

from homeassistant.components.acaia import coordinator as acaia_coordinator
from homeassistant.components.acaia.const import CONF_IDLE_TIMEOUT
from homeassistant.components.acaia.coordinator import SCALE_OFF_AFTER_SILENCE
from homeassistant.components.bluetooth import SOURCE_LOCAL
from homeassistant.core import HomeAssistant


@pytest.fixture
def monotonic_time() -> Generator[MagicMock]:
    """Mock the monotonic clock of the coordinator."""
    with patch.object(
        acaia_coordinator, "MONOTONIC_TIME", return_value=1000.0
    ) as monotonic_time:
        yield monotonic_time


def _advertise(hass: HomeAssistant, time: float) -> None:
    """Inject an advertisement from the scale, always with the same data."""
    inject_advertisement_with_time_and_source(
        hass,
        generate_ble_device("aa:bb:cc:dd:ee:ff", "LUNAR-DDEEFF"),
        generate_advertisement_data(local_name="LUNAR-DDEEFF"),
        time,
        SOURCE_LOCAL,
    )


def _track_connection_state(mock_scale: MagicMock) -> None:
    """Make the mocked scale report its connection state like the real one."""

    async def _connect(**kwargs: Any) -> None:
        mock_scale.connected = True

    async def _disconnect() -> None:
        mock_scale.connected = False

    mock_scale.connect.side_effect = _connect
    mock_scale.disconnect.side_effect = _disconnect


async def _setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    **options: Any,
) -> None:
    """Set up the integration with the given options."""
    _track_connection_state(mock_scale)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, options=options)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float
) -> None:
    """Advance time and let the coordinator poll."""
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_no_idle_disconnect_by_default(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an idle scale stays connected without an idle timeout."""
    await _setup(hass, mock_config_entry, mock_scale)

    await _tick(hass, freezer, 24 * 60)

    mock_scale.disconnect.assert_not_called()


async def test_weight_change_resets_idle_timer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test only the time since the last weight change counts as idle."""
    await _setup(hass, mock_config_entry, mock_scale, **{CONF_IDLE_TIMEOUT: 5})
    notify = acaia_coordinator.AcaiaScale.call_args.kwargs["notify_callback"]
    notify()

    await _tick(hass, freezer, 4)
    mock_scale.weight += 1
    notify()
    await _tick(hass, freezer, 4)
    mock_scale.disconnect.assert_not_called()

    # An unchanged weight does not count as activity.
    notify()
    await _tick(hass, freezer, 1)
    mock_scale.disconnect.assert_called_once()


async def _idle_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Set up the integration and let the scale idle out."""
    await _setup(hass, mock_config_entry, mock_scale, **{CONF_IDLE_TIMEOUT: 5})
    await _tick(hass, freezer, 6)
    mock_scale.disconnect.assert_called_once()
    mock_scale.connect.reset_mock()


@pytest.mark.parametrize(
    "polls_during_silence",
    [pytest.param(0, id="resumes_between_polls"), pytest.param(3, id="polled")],
)
async def test_reconnects_after_scale_turns_off_and_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    monotonic_time: MagicMock,
    polls_during_silence: int,
) -> None:
    """Test an idle disconnect holds until the scale has gone silent and returned."""
    await _idle_disconnect(hass, mock_config_entry, mock_scale, freezer)

    for _ in range(polls_during_silence):
        await _tick(hass, freezer, 1)
    mock_scale.connect.assert_not_called()

    _advertise(hass, monotonic_time.return_value + SCALE_OFF_AFTER_SILENCE + 1)
    await _tick(hass, freezer, 1)
    mock_scale.connect.assert_called_once()


async def test_no_reconnect_while_scale_advertises_after_idle_disconnect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    monotonic_time: MagicMock,
) -> None:
    """Test the scale is left alone while it keeps advertising unchanged data."""
    await _idle_disconnect(hass, mock_config_entry, mock_scale, freezer)

    for advertisement in range(1, 6):
        _advertise(
            hass, monotonic_time.return_value + advertisement * SCALE_OFF_AFTER_SILENCE
        )
        await _tick(hass, freezer, 1)

    mock_scale.connect.assert_not_called()


async def test_no_advertising_while_connected_does_not_count_as_turned_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
    monotonic_time: MagicMock,
) -> None:
    """Test silence from before the disconnect is ignored."""
    await _setup(hass, mock_config_entry, mock_scale, **{CONF_IDLE_TIMEOUT: 5})
    _advertise(hass, monotonic_time.return_value - 10 * SCALE_OFF_AFTER_SILENCE)
    await _tick(hass, freezer, 6)
    mock_scale.disconnect.assert_called_once()
    mock_scale.connect.reset_mock()

    _advertise(hass, monotonic_time.return_value + 1)
    await _tick(hass, freezer, 1)

    mock_scale.connect.assert_not_called()


async def test_unload_disconnects_scale(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
) -> None:
    """Test unloading releases the connection."""
    await _setup(hass, mock_config_entry, mock_scale)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_scale.disconnect.assert_called_once()


async def test_unload_cancels_pending_poll_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading does not wait for a slow connect from polling."""
    await _setup(hass, mock_config_entry, mock_scale)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def _connect(**kwargs: Any) -> None:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    mock_scale.connected = False
    mock_scale.connect.side_effect = _connect

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await started.wait()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert cancelled.is_set()


async def test_connect_completing_after_stop_disconnects(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_scale: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a connection that completes after stopping is released."""
    await _setup(hass, mock_config_entry, mock_scale)
    started = asyncio.Event()
    release = asyncio.Event()

    async def _connect(**kwargs: Any) -> None:
        started.set()
        await release.wait()
        mock_scale.connected = True

    mock_scale.connected = False
    mock_scale.connect.side_effect = _connect

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await started.wait()

    await mock_config_entry.runtime_data.async_stop()
    mock_scale.disconnect.assert_not_called()

    release.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_scale.disconnect.assert_called_once()
    assert mock_scale.connected is False
