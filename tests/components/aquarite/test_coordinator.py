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

from .conftest import MOCK_POOL_ID


@pytest.fixture
def coordinator(
    hass: HomeAssistant,
    mock_pool_data: dict[str, Any],
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
