"""Tests for the Aquarite coordinator.

These tests require the Home Assistant test framework (pytest-homeassistant-custom-component).
Run with: pytest tests/test_coordinator.py (requires HA test environment)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from .conftest import MOCK_POOL_ID

# Skip the entire module if Home Assistant is not installed
pytest.importorskip("homeassistant")

from custom_components.aquarite.coordinator import AquariteDataUpdateCoordinator  # noqa: E402


@pytest.fixture
def coordinator(
    hass,
    mock_pool_data,
) -> AquariteDataUpdateCoordinator:
    """Create a coordinator with mock dependencies."""
    mock_auth = AsyncMock()
    mock_auth.is_token_expiring = MagicMock(return_value=False)
    mock_auth.calculate_sleep_duration = MagicMock(return_value=3600)
    mock_auth.get_client = AsyncMock(return_value=(MagicMock(), False))

    mock_api = AsyncMock()
    mock_api.subscribe_pool = AsyncMock(return_value=MagicMock())
    mock_api.set_value = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"
    mock_entry.options = {}

    coord = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, mock_api, MOCK_POOL_ID
    )
    coord.data = mock_pool_data
    return coord


async def test_subscribe(coordinator: AquariteDataUpdateCoordinator) -> None:
    """Test subscribe calls the API."""
    await coordinator.subscribe()
    coordinator.api.subscribe_pool.assert_called_once()


async def test_refresh_subscription(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test refresh_subscription unsubscribes and resubscribes."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.refresh_subscription()

    mock_to_thread.assert_called_once_with(mock_watch.unsubscribe)
    coordinator.api.subscribe_pool.assert_called_once()


async def test_async_shutdown(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown cancels tasks and unsubscribes."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    mock_health_task = AsyncMock()
    mock_token_task = AsyncMock()
    coordinator._health_task = mock_health_task
    coordinator._token_task = mock_token_task

    with patch("asyncio.to_thread", new_callable=AsyncMock):
        await coordinator.async_shutdown()

    mock_health_task.cancel.assert_called_once()
    mock_token_task.cancel.assert_called_once()


async def test_set_pool_time_to_now(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test set_pool_time_to_now writes a local timestamp."""
    with patch("custom_components.aquarite.coordinator.dt_util") as mock_dt:
        tz = timezone(timedelta(hours=2))
        fake_now = datetime(2026, 4, 12, 14, 30, 0, tzinfo=tz)
        mock_dt.now.return_value = fake_now

        await coordinator.set_pool_time_to_now()

    coordinator.api.set_value.assert_called_once()
    call_args = coordinator.api.set_value.call_args
    assert call_args[0][0] == MOCK_POOL_ID
    assert call_args[0][1] == "main.localTime"

    utc_timestamp = int(fake_now.timestamp())
    expected = utc_timestamp + 7200
    assert call_args[0][2] == expected
