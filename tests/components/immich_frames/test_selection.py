"""Test Immich Frames source and pairing selection."""

from copy import copy
from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aioimmich.assets.models import AssetType, ExifInfo
import pytest

from homeassistant.components.immich_frames.const import (
    CONF_ALBUM_IDS,
    CONF_MODE,
    CONF_ORIENTATION,
    CONF_PAIR_WINDOW,
    CONF_SOURCE,
    CONF_TIME_RANGE,
    MODE_PAIRS,
    MODE_PAIRS_ONLY,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_PORTRAIT,
    ORIENTATION_SQUARE,
    SOURCE_ALBUM,
    SOURCE_SMART,
)
from homeassistant.components.immich_frames.selection import (
    UnsupportedSourceError,
    _cutoff,
    _filter_assets,
    _orientation,
    async_get_candidates,
    candidates_with_companion,
    choose_asset,
    choose_companion,
    selected_photos,
)
from homeassistant.util import dt as dt_util

from tests.components.immich import const as immich_const

MOCK_SEARCH_ASSETS = immich_const.MOCK_SEARCH_ASSETS


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
        dt_util.utcnow(),
    )

    assert candidates == MOCK_SEARCH_ASSETS
    search.async_get_all_by_album_ids.assert_awaited_once_with(
        ["album-1"], page_size=100, max_pages=20
    )


@pytest.mark.asyncio
async def test_empty_album_source_does_not_fall_back_to_all_photos() -> None:
    """An empty persisted album selection must not query the whole library."""
    search = SimpleNamespace(async_get_all_by_album_ids=AsyncMock())

    assert (
        await async_get_candidates(
            SimpleNamespace(search=search),
            {CONF_SOURCE: SOURCE_ALBUM, CONF_ALBUM_IDS: []},
            dt_util.utcnow(),
        )
        == []
    )
    search.async_get_all_by_album_ids.assert_not_awaited()


@pytest.mark.asyncio
async def test_smart_source_uses_image_search() -> None:
    """Keyword selection must use Immich's supported smart-search API."""
    search = SimpleNamespace(
        async_smart_search=AsyncMock(return_value=MOCK_SEARCH_ASSETS)
    )
    api = SimpleNamespace(search=search)

    candidates = await async_get_candidates(
        api,
        {CONF_SOURCE: SOURCE_SMART, "smart_query": "beach"},
        dt_util.utcnow(),
    )

    assert candidates == MOCK_SEARCH_ASSETS
    search.async_smart_search.assert_awaited_once()


@pytest.mark.asyncio
async def test_memories_source_is_not_offered_without_client_support() -> None:
    """Do not silently call an undocumented Immich endpoint."""
    with pytest.raises(UnsupportedSourceError):
        await async_get_candidates(
            SimpleNamespace(), {CONF_SOURCE: "memories"}, dt_util.utcnow()
        )


@pytest.mark.asyncio
async def test_unknown_source_is_rejected() -> None:
    """Do not expose the full library for an invalid persisted source."""
    search = SimpleNamespace(async_get_all=AsyncMock())
    with pytest.raises(UnsupportedSourceError):
        await async_get_candidates(
            SimpleNamespace(search=search),
            {CONF_SOURCE: "unexpected"},
            dt_util.utcnow(),
        )
    search.async_get_all.assert_not_awaited()


def test_portrait_companion_must_have_a_different_checksum() -> None:
    """Pairing avoids duplicate assets returned by Immich."""
    primary, duplicate = (copy(asset) for asset in MOCK_SEARCH_ASSETS[:2])
    primary.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    duplicate.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    duplicate.checksum = primary.checksum

    assert choose_companion(primary, [primary, duplicate], 2) is None


def test_orientation_and_calendar_cutoff_helpers() -> None:
    """Cover orientation detection and month-aware date boundaries."""
    square = copy(MOCK_SEARCH_ASSETS[0])
    square.exif_info = ExifInfo(exif_image_width=100, exif_image_height=100)
    landscape = copy(MOCK_SEARCH_ASSETS[0])
    landscape.exif_info = ExifInfo(exif_image_width=200, exif_image_height=100)
    rotated = copy(landscape)
    rotated.exif_info = ExifInfo(
        exif_image_width=200, exif_image_height=100, orientation="6"
    )
    portrait = copy(MOCK_SEARCH_ASSETS[0])
    portrait.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)

    assert _orientation(square) == ORIENTATION_SQUARE
    assert _orientation(landscape) == ORIENTATION_LANDSCAPE
    assert _orientation(rotated) == ORIENTATION_PORTRAIT
    assert _orientation(portrait) == ORIENTATION_PORTRAIT
    assert _cutoff(datetime(2024, 3, 31, tzinfo=UTC), "1_month") == datetime(
        2024, 2, 29, tzinfo=UTC
    )
    assert _cutoff(dt_util.utcnow(), "all_time") is None


def test_filter_assets_excludes_unsafe_and_mismatched_candidates() -> None:
    """Filter videos, unavailable assets, future dates, and orientations."""
    now = datetime(2023, 2, 15, tzinfo=UTC)
    valid = copy(MOCK_SEARCH_ASSETS[0])
    valid.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    video = copy(valid)
    video.asset_type = AssetType.VIDEO
    trashed = copy(valid)
    trashed.is_trashed = True
    offline = copy(valid)
    offline.is_offline = True
    future = copy(valid)
    future.local_datetime = datetime(2023, 2, 16, tzinfo=UTC)
    landscape = copy(valid)
    landscape.exif_info = ExifInfo(exif_image_width=200, exif_image_height=100)

    assert _filter_assets(
        [valid, video, trashed, offline, future, landscape],
        {CONF_TIME_RANGE: "all_time", CONF_ORIENTATION: ORIENTATION_PORTRAIT},
        now,
    ) == [valid]


def test_filter_assets_compares_immich_wall_clock_values() -> None:
    """Do not convert Immich's local capture time into a UTC instant."""
    now = datetime(2023, 2, 15, 10, 30, tzinfo=timezone(timedelta(hours=2)))
    captured = copy(MOCK_SEARCH_ASSETS[0])
    captured.local_datetime = datetime(2023, 2, 15, 10, 0)
    captured.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)

    assert _filter_assets(
        [captured],
        {CONF_TIME_RANGE: "all_time", CONF_ORIENTATION: ORIENTATION_PORTRAIT},
        now,
    ) == [captured]

    offset_capture = copy(captured)
    offset_capture.local_datetime = datetime(
        2023, 2, 15, 10, 0, tzinfo=timezone(timedelta(hours=2))
    )
    assert _filter_assets(
        [offset_capture],
        {CONF_TIME_RANGE: "all_time", CONF_ORIENTATION: ORIENTATION_PORTRAIT},
        now,
    ) == [offset_capture]


def test_choose_asset_supports_order_and_empty_candidates() -> None:
    """Deterministic ordering modes should be stable and validated."""
    first, second = MOCK_SEARCH_ASSETS[:2]
    with pytest.raises(LookupError):
        choose_asset([], {}, set())
    assert choose_asset([first, second], {"order_direction": "asc"}, set()) is first
    assert choose_asset([first, second], {"order_direction": "desc"}, set()) is second
    assert (
        choose_asset([first, second], {"order_direction": "asc"}, {first.asset_id})
        is second
    )
    assert (
        choose_asset([first, second], {"order_direction": "desc"}, {second.asset_id})
        is first
    )


def test_pair_modes_select_a_valid_companion() -> None:
    """Single-and-pair modes should render the closest valid portrait pair."""
    primary, companion = (copy(asset) for asset in MOCK_SEARCH_ASSETS[:2])
    primary.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    companion.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
    companion.local_datetime = primary.local_datetime
    companion.checksum = "different"

    options = {CONF_MODE: MODE_PAIRS, CONF_PAIR_WINDOW: 2}
    assert selected_photos(primary, [primary, companion], options) == (
        primary,
        companion,
    )
    assert selected_photos(primary, [primary], {CONF_MODE: "single"}) == (primary,)
    with pytest.raises(LookupError):
        selected_photos(primary, [primary], {CONF_MODE: MODE_PAIRS_ONLY})


def test_pairs_only_candidates_are_filtered_without_duplicate_companions() -> None:
    """Pairs-only candidates retain only portraits with a valid partner."""
    primary, companion = (copy(asset) for asset in MOCK_SEARCH_ASSETS[:2])
    for asset in (primary, companion):
        asset.exif_info = ExifInfo(exif_image_width=100, exif_image_height=200)
        asset.local_datetime = primary.local_datetime
    companion.checksum = "different"

    assert candidates_with_companion([primary, companion], {CONF_PAIR_WINDOW: 2}) == [
        primary,
        companion,
    ]
    assert (
        candidates_with_companion([primary, copy(primary)], {CONF_PAIR_WINDOW: 2}) == []
    )
