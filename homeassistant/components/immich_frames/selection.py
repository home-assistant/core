"""Photo selection rules for Immich Frames."""

from calendar import monthrange
from datetime import UTC, datetime
import random

from aioimmich.assets.models import AssetType, ImmichAsset

from .const import (
    CONF_ALBUM_IDS,
    CONF_MODE,
    CONF_ORIENTATION,
    CONF_PAIR_WINDOW,
    CONF_SMART_QUERY,
    CONF_SOURCE,
    CONF_TIME_RANGE,
    DEFAULT_MODE,
    DEFAULT_ORIENTATION,
    DEFAULT_PAIR_WINDOW,
    DEFAULT_SOURCE,
    DEFAULT_TIME_RANGE,
    MODE_PAIRS,
    MODE_PAIRS_ONLY,
    ORIENTATION_ANY,
    ORIENTATION_LANDSCAPE,
    ORIENTATION_PORTRAIT,
    ORIENTATION_SQUARE,
    SOURCE_ALBUM,
    SOURCE_MEMORIES,
    SOURCE_SMART,
)


class UnsupportedSourceError(ValueError):
    """Raised when the installed Immich client lacks a source API."""


def _as_utc(value: datetime) -> datetime:
    """Normalize timestamps for comparisons."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _orientation(asset: ImmichAsset) -> str | None:
    """Return the source image orientation when EXIF dimensions are available."""
    exif = asset.exif_info
    if exif is None or not exif.exif_image_width or not exif.exif_image_height:
        return None
    width, height = exif.exif_image_width, exif.exif_image_height
    if width == height:
        return ORIENTATION_SQUARE
    return ORIENTATION_LANDSCAPE if width > height else ORIENTATION_PORTRAIT


def _cutoff(now: datetime, value: str) -> datetime | None:
    """Calculate a rolling calendar-month cutoff."""
    months = {
        "all_time": 0,
        "1_month": 1,
        "3_months": 3,
        "6_months": 6,
        "1_year": 12,
        "2_years": 24,
        "3_years": 36,
        "4_years": 48,
        "5_years": 60,
        "10_years": 120,
    }.get(value, 0)
    if not months:
        return None
    month_index = now.year * 12 + now.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return now.replace(
        year=year,
        month=month,
        day=min(now.day, monthrange(year, month)[1]),
    )


def _filter_assets(
    assets: list[ImmichAsset], options: dict[str, object], now: datetime
) -> list[ImmichAsset]:
    """Apply frame-wide safety, time, and orientation constraints."""
    orientation = str(options.get(CONF_ORIENTATION, DEFAULT_ORIENTATION))
    cutoff = _cutoff(now, str(options.get(CONF_TIME_RANGE, DEFAULT_TIME_RANGE)))
    current = _as_utc(now)
    result: list[ImmichAsset] = []
    for asset in assets:
        if (
            asset.asset_type is not AssetType.IMAGE
            or asset.is_trashed
            or asset.is_offline
        ):
            continue
        captured = _as_utc(asset.local_datetime)
        if cutoff is not None and captured < _as_utc(cutoff):
            continue
        detected = _orientation(asset)
        if orientation != ORIENTATION_ANY and detected not in (orientation, None):
            continue
        if captured > current:
            continue
        result.append(asset)
    return result


async def async_get_candidates(
    api: object, options: dict[str, object], now: datetime
) -> list[ImmichAsset]:
    """Retrieve candidates through the existing aioimmich client."""
    source = str(options.get(CONF_SOURCE, DEFAULT_SOURCE))
    if source == SOURCE_MEMORIES:
        raise UnsupportedSourceError(
            "The installed aioimmich release does not expose Immich memories."
        )
    search = api.search  # type: ignore[attr-defined]
    if source == SOURCE_ALBUM:
        raw_album_ids = options.get(CONF_ALBUM_IDS, [])
        album_ids = [
            album_id
            for album_id in (raw_album_ids if isinstance(raw_album_ids, list) else [])
            if isinstance(album_id, str) and album_id
        ]
        assets = await search.async_get_all_by_album_ids(
            album_ids, page_size=100, max_pages=20
        )
    elif source == SOURCE_SMART:
        query = str(options.get(CONF_SMART_QUERY, "")).strip()
        assets = await search.async_smart_search(
            query,
            page_size=100,
            max_pages=20,
            asset_type=AssetType.IMAGE,
        )
    else:
        assets = await search.async_get_all(page_size=100, max_pages=20)
    return _filter_assets(assets, options, now)


def choose_asset(
    candidates: list[ImmichAsset], options: dict[str, object], recent_ids: set[str]
) -> ImmichAsset:
    """Choose the next candidate while avoiding recent slides."""
    if not candidates:
        raise LookupError("no photos")
    order = str(options.get("order_direction", "random"))
    if order == "asc":
        return min(candidates, key=lambda asset: asset.local_datetime)
    if order == "desc":
        return max(candidates, key=lambda asset: asset.local_datetime)
    available = [asset for asset in candidates if asset.asset_id not in recent_ids]
    return random.SystemRandom().choice(available or candidates)


def choose_companion(
    primary: ImmichAsset, candidates: list[ImmichAsset], window_days: int
) -> ImmichAsset | None:
    """Find the closest portrait companion within the configured date window."""
    if _orientation(primary) != ORIENTATION_PORTRAIT:
        return None
    eligible = [
        asset
        for asset in candidates
        if asset.asset_id != primary.asset_id
        and _orientation(asset) == ORIENTATION_PORTRAIT
        and asset.checksum != primary.checksum
        and abs((_as_utc(asset.local_datetime) - _as_utc(primary.local_datetime)).days)
        <= window_days
    ]
    return min(
        eligible,
        key=lambda asset: abs(
            (
                _as_utc(asset.local_datetime) - _as_utc(primary.local_datetime)
            ).total_seconds()
        ),
        default=None,
    )


def selected_photos(
    primary: ImmichAsset,
    candidates: list[ImmichAsset],
    options: dict[str, object],
) -> tuple[ImmichAsset, ...]:
    """Return the primary photo plus an optional portrait companion."""
    mode = str(options.get(CONF_MODE, DEFAULT_MODE))
    if mode not in (MODE_PAIRS, MODE_PAIRS_ONLY):
        return (primary,)
    raw_window = options.get(CONF_PAIR_WINDOW, DEFAULT_PAIR_WINDOW)
    window = (
        int(raw_window) if isinstance(raw_window, (int, str)) else DEFAULT_PAIR_WINDOW
    )
    companion = choose_companion(primary, candidates, window)
    if companion is None and mode == MODE_PAIRS_ONLY:
        raise LookupError("no companion")
    return (primary, companion) if companion else (primary,)
