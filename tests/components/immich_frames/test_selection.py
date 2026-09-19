"""Test Immich Frames source and pairing selection."""

from copy import copy
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aioimmich.assets.models import ExifInfo
import pytest

from homeassistant.components.immich_frames.const import (
    CONF_ALBUM_IDS,
    CONF_SOURCE,
    SOURCE_ALBUM,
    SOURCE_SMART,
)
from homeassistant.components.immich_frames.selection import (
    UnsupportedSourceError,
    async_get_candidates,
    choose_companion,
)

from tests.components.immich.const import MOCK_SEARCH_ASSETS


@pytest.mark.asyncio
async def test_album_source_uses_selected_albums() -> None:
    """Album selection must use the shared client's album search method."""
    search = SimpleNamespace(
        async_get_all_by_album_ids=AsyncMock(return_value=MOCK_SEARCH_ASSETS)
    )
    api = SimpleNamespace(search=search)

    candidates = await async_get_candidates(
        api,
        {CONF_SOURCE: SOURCE_ALBUM, CONF_ALBUM_IDS: ["album-1"]},
        datetime.now(UTC),
    )

    assert candidates == MOCK_SEARCH_ASSETS
    search.async_get_all_by_album_ids.assert_awaited_once_with(
        ["album-1"], page_size=100, max_pages=20
    )


@pytest.mark.asyncio
async def test_smart_source_uses_image_search() -> None:
    """Keyword selection must use Immich's supported smart-search API."""
    search = SimpleNamespace(async_smart_search=AsyncMock(return_value=MOCK_SEARCH_ASSETS))
    api = SimpleNamespace(search=search)

    candidates = await async_get_candidates(
        api,
        {CONF_SOURCE: SOURCE_SMART, "smart_query": "beach"},
        datetime.now(UTC),
    )

    assert candidates == MOCK_SEARCH_ASSETS
    search.async_smart_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_memories_source_is_not_offered_without_client_support() -> None:
    """Do not silently call an undocumented Immich endpoint."""
    with pytest.raises(UnsupportedSourceError):
        await async_get_candidates(
            SimpleNamespace(), {CONF_SOURCE: "memories"}, datetime.now(UTC)
        )


def test_portrait_companion_must_have_a_different_checksum() -> None:
    """Pairing avoids duplicate assets returned by Immich."""
    primary, duplicate = (copy(asset) for asset in MOCK_SEARCH_ASSETS[:2])
    primary.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    duplicate.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    duplicate.checksum = primary.checksum

    assert choose_companion(primary, [primary, duplicate], 2) is None
