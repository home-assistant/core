"""Tests for the Aquarite coordinator.

These tests run in the Home Assistant Core test environment.
Run with: pytest tests/components/aquarite/test_coordinator.py
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from homeassistant.components.aquarite.const import CONF_HEALTH_CHECK_INTERVAL
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
    mock_api.fetch_pool_data = AsyncMock(return_value=mock_pool_data)
    mock_api.set_value = AsyncMock()

    mock_entry = MagicMock()
    mock_entry.entry_id = "test"
    mock_entry.options = {}

    coord = AquariteDataUpdateCoordinator(
        hass, mock_entry, mock_auth, mock_api, MOCK_POOL_ID
    )
    coord.data = mock_pool_data
    return coord


# ── Basic API methods ───────────────────────────────────────────


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
    coordinator.api.subscribe_pool.assert_called_once()
    assert coordinator.watch is not None


async def test_subscribe_callback_pushes_data_to_loop(
    hass: HomeAssistant,
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the _on_data callback inside subscribe pushes data to the HA loop."""
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


# ── Background task lifecycle ──────────────────────────────────


async def test_setup_tasks_creates_background_tasks(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test setup_tasks creates both background tasks."""
    with patch.object(coordinator.hass, "async_create_background_task") as mock_create:
        await coordinator.setup_tasks()

    assert mock_create.call_count == 2
    names = [call.args[1] for call in mock_create.call_args_list]
    assert "Aquarite health check" in names
    assert "Aquarite token refresh" in names


# ── Token refresh loop ─────────────────────────────────────────


async def test_token_refresh_loop_refreshes_when_expiring(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the loop refreshes the token when expiring and resubscribes."""
    coordinator.auth.is_token_expiring = MagicMock(return_value=True)
    coordinator.auth.get_client = AsyncMock(return_value=(MagicMock(), True))
    coordinator.refresh_subscription = AsyncMock()
    coordinator.auth.calculate_sleep_duration = MagicMock(return_value=0)

    # Stop after one iteration
    with (
        patch.object(
            type(coordinator.hass), "is_stopping", new_callable=PropertyMock
        ) as mock_stop,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_stop.side_effect = [False, True]
        await coordinator._token_refresh_loop()

    coordinator.auth.get_client.assert_awaited_once()
    coordinator.refresh_subscription.assert_awaited_once()
    mock_sleep.assert_awaited()


async def test_token_refresh_loop_no_refresh_needed(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the loop sleeps when token is not expiring."""
    coordinator.auth.is_token_expiring = MagicMock(return_value=False)
    coordinator.refresh_subscription = AsyncMock()

    with (
        patch.object(
            type(coordinator.hass), "is_stopping", new_callable=PropertyMock
        ) as mock_stop,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_stop.side_effect = [False, True]
        await coordinator._token_refresh_loop()

    coordinator.auth.get_client.assert_not_called()
    coordinator.refresh_subscription.assert_not_called()
    mock_sleep.assert_awaited()


async def test_token_refresh_loop_handles_exception(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the loop catches exceptions and applies exponential backoff."""
    coordinator.auth.is_token_expiring = MagicMock(side_effect=RuntimeError("boom"))

    with (
        patch.object(
            type(coordinator.hass), "is_stopping", new_callable=PropertyMock
        ) as mock_stop,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_stop.side_effect = [False, True]
        await coordinator._token_refresh_loop()

    # Slept with the retry_delay (10 seconds initial backoff)
    mock_sleep.assert_awaited_with(10)


# ── Periodic health check ──────────────────────────────────────


async def test_periodic_health_check_success(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the health check sleeps and pings get_client."""
    coordinator.refresh_subscription = AsyncMock()

    with (
        patch.object(
            type(coordinator.hass), "is_stopping", new_callable=PropertyMock
        ) as mock_stop,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_stop.side_effect = [False, True]
        await coordinator.periodic_health_check()

    mock_sleep.assert_awaited()
    coordinator.auth.get_client.assert_awaited_once()
    coordinator.refresh_subscription.assert_not_called()


async def test_periodic_health_check_uses_options_interval(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the health check uses the configured interval from options."""
    coordinator.config_entry.options = {CONF_HEALTH_CHECK_INTERVAL: 600}

    with (
        patch.object(
            type(coordinator.hass), "is_stopping", new_callable=PropertyMock
        ) as mock_stop,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        mock_stop.side_effect = [False, True]
        await coordinator.periodic_health_check()

    mock_sleep.assert_awaited_with(600)


async def test_periodic_health_check_resubscribes_on_error(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test the health check resubscribes when get_client raises."""
    coordinator.auth.get_client = AsyncMock(side_effect=RuntimeError("network"))
    coordinator.refresh_subscription = AsyncMock()

    with (
        patch.object(
            type(coordinator.hass), "is_stopping", new_callable=PropertyMock
        ) as mock_stop,
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        mock_stop.side_effect = [False, True]
        await coordinator.periodic_health_check()

    coordinator.refresh_subscription.assert_awaited_once()


# ── Subscription management ────────────────────────────────────


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


async def test_refresh_subscription_no_existing_watch(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test refresh_subscription skips unsubscribe when no watch exists."""
    coordinator.watch = None

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.refresh_subscription()

    mock_to_thread.assert_not_called()
    coordinator.api.subscribe_pool.assert_called_once()


# ── Shutdown ───────────────────────────────────────────────────


async def test_async_shutdown(
    hass: HomeAssistant,
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown cancels tasks and unsubscribes."""
    mock_watch = MagicMock()
    coordinator.watch = mock_watch

    async def _never_ending() -> None:
        await asyncio.sleep(3600)

    health_task = hass.async_create_task(_never_ending())
    token_task = hass.async_create_task(_never_ending())
    coordinator._health_task = health_task
    coordinator._token_task = token_task

    with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
        await coordinator.async_shutdown()

    assert health_task.cancelled()
    assert token_task.cancelled()
    mock_to_thread.assert_called_once_with(mock_watch.unsubscribe)
    assert coordinator.watch is None


async def test_async_shutdown_no_tasks_or_watch(
    coordinator: AquariteDataUpdateCoordinator,
) -> None:
    """Test shutdown is a no-op when there are no tasks or watch."""
    coordinator._health_task = None
    coordinator._token_task = None
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
