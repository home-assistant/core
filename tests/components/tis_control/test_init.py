"""Tests for the TIS Control integration."""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.tis_control import async_setup_entry, async_unload_entry
from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, async_capture_events


async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test successful setup of entry."""
    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_tis_api.connect.assert_awaited_once()
        mock_tis_api.scan_devices.assert_awaited_once()
        mock_forward.assert_called_once()
        assert mock_config_entry.runtime_data.tis_api == mock_tis_api


async def test_async_setup_entry_connect_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test unsuccessful setup due to connection failure."""
    mock_tis_api.connect.side_effect = ConnectionError("Test error")

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        pytest.raises(
            ConfigEntryNotReady,
            match="Unable to connect to TIS Control on port 6000: Test error",
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)

    mock_tis_api.scan_devices.assert_not_called()
    mock_forward.assert_not_called()


async def test_async_setup_entry_scan_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test setup proceeds even if scan_devices fails."""
    mock_tis_api.scan_devices.side_effect = ConnectionError("Scan failed")

    with patch.object(
        hass.config_entries, "async_forward_entry_setups"
    ) as mock_forward:
        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_tis_api.scan_devices.assert_awaited_once()
        mock_forward.assert_called_once()


async def test_async_setup_entry_forward_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test setup exception during forward setups."""
    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            side_effect=Exception("Forward failed"),
        ),
        pytest.raises(Exception, match="Forward failed"),
    ):
        await async_setup_entry(hass, mock_config_entry)

    mock_tis_api.disconnect.assert_called_once()
    assert mock_config_entry.runtime_data.listener_task is None


async def test_async_setup_entry_event_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test that the background task consumes events and fires bus events."""
    fake_event = {"device_id": "test_device", "value": 1}

    # Yield one event then exit the generator
    async def _mock_event_generator():
        yield fake_event

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    event_type = f"{DOMAIN}_event"
    captured_events = async_capture_events(hass, event_type)

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

    assert len(captured_events) == 1
    assert captured_events[0].data == fake_event

    # Cleanup: unload the entry to stop the background task
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()


async def test_async_unload_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.listener_task = None

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_config_entry)
        assert result is True
        mock_config_entry.runtime_data.tis_api.disconnect.assert_called_once()


async def test_async_unload_entry_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unsuccessful unload of entry."""
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.listener_task = None

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is False
        mock_unload_platforms.assert_called_once()
        mock_config_entry.runtime_data.tis_api.disconnect.assert_not_called()


async def test_async_setup_entry_event_listener_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tis_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the background task handles exceptions when processing events."""
    fake_event = {"value": 1}

    async def _mock_event_generator():
        yield fake_event

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    # Patch async_fire to raise an exception when called
    with (
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch(
            "homeassistant.core.EventBus.async_fire",
            side_effect=Exception("Simulated bus error"),
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

    # Verify that the exception was caught and logged.
    assert "Unexpected error while processing TIS event" in caplog.text

    # Cleanup: unload the entry to stop the background task
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()


async def test_async_setup_entry_event_listener_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tis_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the background task handles cancellation correctly."""

    # Loop forever until cancelled
    async def _mock_event_generator():
        while True:
            await asyncio.sleep(0)
            yield {"test": "event"}

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        caplog.at_level(logging.DEBUG),
    ):
        await async_setup_entry(hass, mock_config_entry)

        # The task is stored in runtime_data
        task = mock_config_entry.runtime_data.listener_task
        assert task is not None
        assert not task.done()

        # Unload the entry, which should cancel the task
        with patch.object(
            hass.config_entries, "async_unload_platforms", return_value=True
        ):
            await async_unload_entry(hass, mock_config_entry)

        await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that the cancel debug message was logged.
    assert "TIS event listener task cancelled" in caplog.text


async def test_async_setup_entry_event_listener_generator_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tis_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the background task restarts the generator on failure."""

    # Track calls to consume_events
    call_count = 0

    async def _mock_event_generator():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: yield one event then fail
            yield {"event": 1}
            raise RuntimeError("Generator crash")
        # Second call: hang to prevent further restarts during test
        await asyncio.Event().wait()

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups"),
        patch(
            "homeassistant.components.tis_control.asyncio.sleep",
            side_effect=lambda _: asyncio.sleep(0),
        ),
    ):
        await async_setup_entry(hass, mock_config_entry)

        # Give the loop a chance to run and restart
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    # Verify that the exception was logged.
    assert "Unexpected error in TIS event listener, restarting in 1s" in caplog.text
    assert call_count >= 2

    # Cleanup: unload the entry to stop the background task
    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        await async_unload_entry(hass, mock_config_entry)
        await hass.async_block_till_done()
