"""Test VRChat world data."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.vrchat.api_data_types import World
from homeassistant.components.vrchat.world import (
    VRCHAT_WORLD_DATA_CACHE_TTL,
    VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND,
    VRChatWorldData,
)
from homeassistant.util import dt as dt_util


@pytest.fixture(autouse=True)
def clear_world_data() -> None:
    """Clear cached world data."""
    VRChatWorldData.registry.clear()
    VRChatWorldData.last_pruned = datetime.min.replace(tzinfo=UTC)


@pytest.mark.parametrize(
    ("subscribe", "expected_retained"),
    [
        pytest.param(False, False, id="no_subscribers"),
        pytest.param(True, True, id="subscribed"),
    ],
)
def test_get_prunes_expired_unused_world_data(
    subscribe: bool, expected_retained: bool
) -> None:
    """Test expired world data is pruned when the cache is next accessed."""
    world = VRChatWorldData.get("wrld_expired")
    world.last_updated = dt_util.utcnow() - VRCHAT_WORLD_DATA_CACHE_TTL
    if subscribe:
        world.subscribe(Mock())
    VRChatWorldData.last_pruned = dt_util.utcnow() - timedelta(
        seconds=VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND
    )

    VRChatWorldData.get("wrld_current")

    assert ("wrld_expired" in VRChatWorldData.registry) is expected_retained


def test_world_data_notifies_subscriber_snapshot() -> None:
    """Test unsubscribing during notification does not skip later subscribers."""
    world = VRChatWorldData.get("wrld_test")
    second_callback = Mock()

    def unsubscribe_second_callback(_: World | None) -> None:
        world.unsubscribe(second_callback)

    world.subscribe(unsubscribe_second_callback)
    world.subscribe(second_callback)

    world.data = None

    second_callback.assert_called_once_with(None)


def test_world_data_subscribe_and_unsubscribe() -> None:
    """Test subscribing and removing the same callback repeatedly."""
    world = VRChatWorldData.get("wrld_test")
    callback = Mock()

    remove_callback = world.subscribe(callback)
    remove_callback()
    remove_callback()
    world.unsubscribe(callback)

    assert not world.subscribers


def test_get_existing_world_updates_data() -> None:
    """Test retrieving an existing world with data updates its cache."""
    world = VRChatWorldData.get("wrld_test", {"id": "wrld_test", "name": "Old"})
    updated = VRChatWorldData.get("wrld_test", {"id": "wrld_test", "name": "New"})

    assert updated is world
    assert world.data == {"id": "wrld_test", "name": "New"}


async def test_get_data_returns_fresh_data_without_fetch() -> None:
    """Test fresh cached world data does not start a fetch task."""
    world = VRChatWorldData.get("wrld_test", {"id": "wrld_test"})

    with patch("homeassistant.components.vrchat.world.VRChatAPI") as api:
        assert await world.get_data() == {"id": "wrld_test"}

    api.assert_not_called()


async def test_get_data_fetches_when_data_is_missing() -> None:
    """Test missing world data is fetched after the WebSocket grace period."""
    api = Mock()
    api.get_world = AsyncMock(return_value={"id": "wrld_test"})
    api_context = MagicMock()
    api_context.__aenter__ = AsyncMock(return_value=api)
    api_context.__aexit__ = AsyncMock(return_value=None)
    world = VRChatWorldData.get("wrld_test")

    with (
        patch(
            "homeassistant.components.vrchat.world.VRChatAPI", return_value=api_context
        ),
        patch("homeassistant.components.vrchat.world.asyncio.sleep", new=AsyncMock()),
    ):
        assert await world.get_data() == {"id": "wrld_test"}

    api.get_world.assert_awaited_once_with("wrld_test")


async def test_get_data_retries_after_timeout() -> None:
    """Test world data fetch retries after a timeout."""
    api = Mock()
    api.get_world = AsyncMock(side_effect=[TimeoutError, {"id": "wrld_test"}])
    api_context = MagicMock()
    api_context.__aenter__ = AsyncMock(return_value=api)
    api_context.__aexit__ = AsyncMock(return_value=None)
    world = VRChatWorldData.get("wrld_test")
    world._data = {"id": "wrld_test"}
    world.last_updated = dt_util.utcnow() - VRCHAT_WORLD_DATA_CACHE_TTL

    with patch(
        "homeassistant.components.vrchat.world.VRChatAPI", return_value=api_context
    ):
        assert await world.get_data() == {"id": "wrld_test"}

    assert api.get_world.await_count == 2
    assert world.task is None


async def test_get_data_retries_after_error() -> None:
    """Test world data fetch retries after a general error."""
    api = Mock()
    api.get_world = AsyncMock(
        side_effect=[RuntimeError("test error"), {"id": "wrld_test"}]
    )
    api_context = MagicMock()
    api_context.__aenter__ = AsyncMock(return_value=api)
    api_context.__aexit__ = AsyncMock(return_value=None)
    world = VRChatWorldData.get("wrld_test")
    world._data = {"id": "wrld_test"}
    world.last_updated = dt_util.utcnow() - VRCHAT_WORLD_DATA_CACHE_TTL

    with (
        patch(
            "homeassistant.components.vrchat.world.VRChatAPI", return_value=api_context
        ),
        patch("homeassistant.components.vrchat.world.asyncio.sleep", new=AsyncMock()),
    ):
        assert await world.get_data() == {"id": "wrld_test"}

    assert api.get_world.await_count == 2


async def test_get_data_clears_task_after_cancellation() -> None:
    """Test cancelling a world data fetch permits a later refresh."""
    fetch_started = asyncio.Event()
    fetch_finished = asyncio.Event()

    async def get_world(_: str) -> None:
        fetch_started.set()
        await fetch_finished.wait()

    api = Mock()
    api.get_world = AsyncMock(side_effect=get_world)
    api_context = MagicMock()
    api_context.__aenter__ = AsyncMock(return_value=api)
    api_context.__aexit__ = AsyncMock(return_value=None)
    world = VRChatWorldData.get("wrld_test")
    world._data = {"id": "wrld_test"}
    world.last_updated = dt_util.utcnow() - VRCHAT_WORLD_DATA_CACHE_TTL

    with patch(
        "homeassistant.components.vrchat.world.VRChatAPI", return_value=api_context
    ):
        task = asyncio.create_task(world.get_data())
        await fetch_started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        api.get_world = AsyncMock(return_value={"id": "wrld_test"})
        assert await world.get_data() == {"id": "wrld_test"}

    assert world.task is None
