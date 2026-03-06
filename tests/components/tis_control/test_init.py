"""Tests for the TIS Control integration."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.tis_control import async_setup_entry, async_unload_entry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from tests.common import MockConfigEntry, async_capture_events


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_async_setup_entry_connect_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test unsuccessful setup due to connection failure."""
    mock_tis_api.connect.side_effect = ConnectionError("Test error")

    with (
        patch.object(hass.config_entries, "async_forward_entry_setups") as mock_forward,
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)

    mock_tis_api.scan_devices.assert_not_called()
    mock_forward.assert_not_called()


@pytest.mark.asyncio
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
        mock_tis_api.scan_devices.assert_called_once()
        mock_forward.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_event_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tis_api: MagicMock
) -> None:
    """Test that the background task consumes events and fires bus events."""
    fake_event = {"device_id": "test_device", "value": 1}

    # Yield one event then exit the generator
    async def _mock_event_generator():
        yield fake_event

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    event_type = "tis_device_test_device"
    captured_events = async_capture_events(hass, event_type)

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert len(captured_events) == 1
    assert captured_events[0].data == fake_event


@pytest.mark.asyncio
async def test_async_unload_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unload of entry."""
    mock_config_entry.runtime_data = MagicMock()

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await async_unload_entry(hass, mock_config_entry)
        assert result is True


@pytest.mark.asyncio
async def test_async_unload_entry_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unsuccessful unload of entry."""
    mock_config_entry.runtime_data = MagicMock()

    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ) as mock_unload_platforms:
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is False
        mock_unload_platforms.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_entry_event_listener_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tis_api: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the background task handles exceptions when processing events."""
    # Yield an event missing 'device_id' to raise a KeyError.
    fake_event = {"value": 1}

    async def _mock_event_generator():
        yield fake_event

    mock_tis_api.consume_events.side_effect = _mock_event_generator

    with patch.object(hass.config_entries, "async_forward_entry_setups"):
        await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done(wait_background_tasks=True)

    # Verify that the exception was caught and logged.
    assert "Unexpected error while processing TIS event" in caplog.text
