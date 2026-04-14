"""Tests for Frontier Silicon media browsing."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, Mock

from afsapi import AFSAPI

from homeassistant.components.frontier_silicon.browse_media import browse_node
from homeassistant.components.frontier_silicon.const import MEDIA_CONTENT_ID_CHANNELS
from homeassistant.components.media_player import MediaClass, MediaType


async def _mock_nav_list() -> AsyncIterator[tuple[str, dict[str, str]]]:
    """Yield a single navigation item."""
    yield "42", {"label": "Station 42", "type": "1"}


async def test_browse_node_iterates_async_generator_nav_list() -> None:
    """Test browse_node handles nav_list as an async generator."""
    afsapi = Mock(spec=AFSAPI)
    afsapi.nav_select_folder_via_path = AsyncMock()
    afsapi.nav_list = _mock_nav_list

    result = await browse_node(
        afsapi,
        MediaType.CHANNELS,
        f"radio/{MEDIA_CONTENT_ID_CHANNELS}",
    )

    afsapi.nav_select_folder_via_path.assert_awaited_once_with([])
    assert result.children is not None
    assert len(result.children) == 1
    assert result.children[0].title == "Station 42"
    assert result.children[0].media_class == MediaClass.CHANNEL
    assert result.children[0].can_play is True
    assert result.children[0].can_expand is False
