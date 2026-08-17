"""Test VRChat world data."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from homeassistant.components.vrchat.world import (
    VRCHAT_WORLD_DATA_CACHE_TTL,
    VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND,
    VRChatWorldData,
)


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
    world.last_updated = datetime.now(UTC) - VRCHAT_WORLD_DATA_CACHE_TTL
    if subscribe:
        world.subscribe(Mock())
    VRChatWorldData.last_pruned = datetime.now(UTC) - timedelta(
        seconds=VRCHAT_WORLD_DATA_OBJECT_PRUNE_INTERVAL_SECOND
    )

    VRChatWorldData.get("wrld_current")

    assert ("wrld_expired" in VRChatWorldData.registry) is expected_retained


async def test_get_data_retries_after_timeout() -> None:
    """Test world data fetch retries after a timeout."""
    api = Mock()
    api.get_world = AsyncMock(side_effect=[TimeoutError, {"id": "wrld_test"}])
    api_context = MagicMock()
    api_context.__aenter__ = AsyncMock(return_value=api)
    api_context.__aexit__ = AsyncMock(return_value=None)
    world = VRChatWorldData.get("wrld_test")
    world._data = {"id": "wrld_test"}
    world.last_updated = datetime.now(UTC) - VRCHAT_WORLD_DATA_CACHE_TTL

    with patch(
        "homeassistant.components.vrchat.world.VRChatAPI", return_value=api_context
    ):
        assert await world.get_data() == {"id": "wrld_test"}

    assert api.get_world.await_count == 2
    assert world.task is None


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
    world.last_updated = datetime.now(UTC) - VRCHAT_WORLD_DATA_CACHE_TTL

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
