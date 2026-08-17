"""Test VRChat world data."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

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
