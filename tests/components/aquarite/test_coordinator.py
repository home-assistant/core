"""Tests for the Aquarite coordinator.

These tests run in the Home Assistant Core test environment.
Run with: pytest tests/components/aquarite/test_coordinator.py
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.aquarite.coordinator import AquariteDataUpdateCoordinator
from homeassistant.core import HomeAssistant

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_pool_data: dict[str, Any],
) -> AquariteDataUpdateCoordinator:
    """Create a coordinator with mock dependencies."""
    mock_auth = AsyncMock()
    mock_api = AsyncMock()
    mock_api.subscribe_pool = AsyncMock(return_value=MagicMock())
    mock_api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"

    coord = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, mock_api, MOCK_POOL_ID, MOCK_POOL_NAME
    )
    coord.data = mock_pool_data
    return coord


# ── Basic methods ──────────────────────────────────────────────


async def test_async_update_data_calls_fetch(
    coordinator: AquariteDataUpdateCoordinator,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test _async_update_data fetches via the API (manual refresh fallback)."""
    result = await coordinator._async_update_data()
    coordinator.api.fetch_pool_data.assert_awaited_once_with(MOCK_POOL_ID)
    assert result is mock_pool_data


async def test_subscribe(coordinator: AquariteDataUpdateCoordinator) -> None:
    """Test subscribe calls the API and stores the watch handle."""
    await coordinator.subscribe()
    coordinator.api.subscribe_pool.assert_awaited_once()
    assert coordinator.watch is not None


async def test_subscribe_callback_pushes_data_to_loop(
    hass: HomeAssistant,
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the _on_data callback pushes data to the HA loop."""
    captured_callback: list[Any] = []

    async def _capture_subscribe(_pool_id: str, callback: Any) -> MagicMock:
        captured_callback.append(callback)
        return MagicMock()

    coordinator.api.subscribe_pool = AsyncMock(side_effect=_capture_subscribe)
    await coordinator.subscribe()

    new_data = {"main": {"temperature": 30.0}}
    captured_callback[0](new_data)
    await hass.async_block_till_done()

    assert coordinator.data == new_data


async def test_refresh_subscription(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test refresh_subscription unsubscribes and resubscribes."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.refresh_subscription()

    mock_to_thread.assert_called_once_with(mock_watch.unsubscribe)
    coordinator.api.subscribe_pool.assert_awaited_once()


async def test_refresh_subscription_no_existing_watch(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test refresh_subscription skips unsubscribe when no watch exists."""
    coordinator.watch = None

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.refresh_subscription()

    mock_to_thread.assert_not_called()
    coordinator.api.subscribe_pool.assert_awaited_once()


async def test_async_shutdown(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown unsubscribes and clears watch."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.async_shutdown()

    mock_to_thread.assert_called_once_with(mock_watch.unsubscribe)
    assert coordinator.watch is None


async def test_async_shutdown_no_watch(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown is a no-op when there is no watch."""
    coordinator.watch = None

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.async_shutdown()

    mock_to_thread.assert_not_called()


# ── get_value helper ───────────────────────────────────────────


def test_get_value_existing(coordinator: AquariteDataUpdateCoordinator) -> None:
    """Test get_value returns nested data using dot-notation."""
    assert coordinator.get_value("main.temperature") == 25.5


def test_get_value_missing_returns_default(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test get_value returns the default when path is absent."""
    assert coordinator.get_value("nonexistent.path") is None
    assert coordinator.get_value("nonexistent.path", "fallback") == "fallback"
