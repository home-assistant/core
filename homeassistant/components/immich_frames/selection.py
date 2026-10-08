"""Photo selection rules for Immich Frames."""

from bisect import bisect_left, bisect_right
from calendar import monthrange
from datetime import datetime
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


_ROTATED_EXIF_ORIENTATIONS = {
    "5",
    "6",
    "7",
    "8",
    "90",
    "-90",
    "270",
    "-270",
    "rotate 90 cw",
    "rotate 90 ccw",
    "rotate 270 cw",
    "rotate 270 ccw",
}


def _as_wall_clock(value: datetime) -> datetime:
    """Treat Immich localDateTime as a timezone-free wall-clock value.

    Immich deliberately stores the local capture time in this field.  The API
    may serialize it as either a naive value or an offset-bearing value, but
    converting it to an instant changes the captured clock time.
    """
    return value.replace(tzinfo=None)


def _wall_clock_seconds(value: datetime) -> float:
    """Return a stable numeric value for a wall-clock timestamp."""
    return (_as_wall_clock(value) - datetime.min).total_seconds()


def _orientation(asset: ImmichAsset) -> str | None:
    """Return the source image orientation when EXIF dimensions are available."""
    exif = asset.exif_info
    if exif is None or not exif.exif_image_width or not exif.exif_image_height:
        return None
    width, height = exif.exif_image_width, exif.exif_image_height
    if str(exif.orientation or "").strip().lower() in _ROTATED_EXIF_ORIENTATIONS:
        width, height = height, width
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
    current = _as_wall_clock(now)
    cutoff = _cutoff(current, str(options.get(CONF_TIME_RANGE, DEFAULT_TIME_RANGE)))
    result: list[ImmichAsset] = []
    for asset in assets:
        if (
            asset.asset_type is not AssetType.IMAGE
            or asset.is_trashed
            or asset.is_offline
        ):
            continue
        captured = _as_wall_clock(asset.local_datetime)
        if cutoff is not None and captured < cutoff:
            continue
        detected = _orientation(asset)
        if orientation not in (ORIENTATION_ANY, detected):
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
        if not album_ids:
            return []
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
    elif source == DEFAULT_SOURCE:
        assets = await search.async_get_all(page_size=100, max_pages=20)
    else:
        raise UnsupportedSourceError(f"Unsupported Immich source: {source}")
    return _filter_assets(assets, options, now)


def choose_asset(
    candidates: list[ImmichAsset], options: dict[str, object], recent_ids: set[str]
) -> ImmichAsset:
    """Choose the next candidate while avoiding recent slides."""
    if not candidates:
        raise LookupError("no photos")
    available = [asset for asset in candidates if asset.asset_id not in recent_ids]
    pool = available or candidates
    order = str(options.get("order_direction", "random"))
    if order == "asc":
        return min(pool, key=lambda asset: _as_wall_clock(asset.local_datetime))
    if order == "desc":
        return max(pool, key=lambda asset: _as_wall_clock(asset.local_datetime))
    return random.SystemRandom().choice(pool)


def candidates_with_companion(
    candidates: list[ImmichAsset], options: dict[str, object]
) -> list[ImmichAsset]:
    """Return candidates that can satisfy pairs-only mode."""
    raw_window = options.get(CONF_PAIR_WINDOW, DEFAULT_PAIR_WINDOW)
    try:
        window = max(0, int(float(str(raw_window))))
    except TypeError, ValueError:
        window = DEFAULT_PAIR_WINDOW
    portrait = sorted(
        (asset for asset in candidates if _orientation(asset) == ORIENTATION_PORTRAIT),
        key=lambda asset: _wall_clock_seconds(asset.local_datetime),
    )
    timestamps = [_wall_clock_seconds(asset.local_datetime) for asset in portrait]
    by_checksum: dict[str, list[float]] = {}
    by_asset_id: dict[str, list[float]] = {}
    by_identity: dict[tuple[str, str], list[float]] = {}
    for asset, timestamp in zip(portrait, timestamps, strict=True):
        by_checksum.setdefault(asset.checksum, []).append(timestamp)
        by_asset_id.setdefault(asset.asset_id, []).append(timestamp)
        by_identity.setdefault((asset.asset_id, asset.checksum), []).append(timestamp)

    def count_in_window(values: list[float], start: float, end: float) -> int:
        """Count sorted timestamps in an inclusive range."""
        return bisect_right(values, end) - bisect_left(values, start)

    result: list[ImmichAsset] = []
    seconds = window * 86400
    for asset in candidates:
        if _orientation(asset) != ORIENTATION_PORTRAIT:
            continue
        timestamp = _wall_clock_seconds(asset.local_datetime)
        start, end = timestamp - seconds, timestamp + seconds
        total = count_in_window(timestamps, start, end)
        same_checksum = count_in_window(by_checksum.get(asset.checksum, []), start, end)
        same_asset = count_in_window(by_asset_id.get(asset.asset_id, []), start, end)
        same_identity = count_in_window(
            by_identity.get((asset.asset_id, asset.checksum), []), start, end
        )
        if total - same_checksum - same_asset + same_identity > 0:
            result.append(asset)
    return result


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
        and abs(
            (
                _as_wall_clock(asset.local_datetime)
                - _as_wall_clock(primary.local_datetime)
            ).total_seconds()
        )
        <= window_days * 86400
    ]
    return min(
        eligible,
        key=lambda asset: abs(
            (
                _as_wall_clock(asset.local_datetime)
                - _as_wall_clock(primary.local_datetime)
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
    try:
        window = max(0, int(float(str(raw_window))))
    except TypeError, ValueError:
        window = DEFAULT_PAIR_WINDOW
    companion = choose_companion(primary, candidates, window)
    if companion is None and mode == MODE_PAIRS_ONLY:
        raise LookupError("no companion")
    return (primary, companion) if companion else (primary,)
