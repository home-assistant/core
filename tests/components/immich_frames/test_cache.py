"""Test Immich Frames cache integrity and invalidation."""

from copy import copy
from datetime import timedelta
from io import BytesIO
from pathlib import Path

from aioimmich.assets.models import ExifInfo
from PIL import Image
import pytest

from homeassistant.components.immich_frames.cache import FrameCache
from homeassistant.components.immich_frames.const import CONF_SCREEN_SHAPE
from homeassistant.components.immich_frames.rendering import render
from homeassistant.util import dt as dt_util

from tests.components.immich import const as immich_const

MOCK_SEARCH_ASSETS = immich_const.MOCK_SEARCH_ASSETS


def test_cache_round_trip_and_settings_invalidation(tmp_path: Path) -> None:
    """A cache entry survives a round trip but not a render setting change."""
    cache = FrameCache(tmp_path / "frame.json")
    asset = MOCK_SEARCH_ASSETS[0]

    # Keep the fixture focused on cache behavior while using a valid contract image.
    payload = BytesIO()
    Image.new("RGB", (16, 12), "red").save(payload, "JPEG")
    image, _ = render([payload.getvalue()], "landscape", "show_full")
    options = {CONF_SCREEN_SHAPE: "landscape"}

    rendered_at = dt_util.utcnow() - timedelta(days=1)
    cache.write(asset, image, options, "parent", "server-a", rendered_at)

    assert cache.read(options, "parent", "server-a") == (asset, image, rendered_at)
    assert cache.read(options, "parent", "server-b") is None
    assert cache.read({CONF_SCREEN_SHAPE: "portrait"}, "parent", "server-a") is None

    cache.clear()
    assert not cache.path.exists()


def test_cache_handles_exif_variants_and_invalid_output(tmp_path: Path) -> None:
    """Cache serialization handles optional and timestamped EXIF metadata."""
    cache = FrameCache(tmp_path / "frame.json")
    asset = copy(MOCK_SEARCH_ASSETS[0])
    asset.exif_info = ExifInfo(date_time_original=dt_util.utcnow())
    payload = BytesIO()
    Image.new("RGB", (16, 12), "blue").save(payload, "JPEG")
    image, _ = render([payload.getvalue()], "landscape", "show_full")
    cache.write(asset, image, {}, "parent", "server", dt_util.utcnow())
    assert (
        cache.read({}, "parent", "server")[0].exif_info.date_time_original is not None
    )

    asset.exif_info = None
    cache.write(asset, image, {}, "parent", "server", dt_util.utcnow())
    assert cache.read({}, "parent", "server")[0].exif_info is None

    invalid = BytesIO()
    Image.new("RGB", (100, 100), "black").save(invalid, "JPEG")
    with pytest.raises(ValueError):
        cache.write(asset, invalid.getvalue(), {}, "parent", "server", dt_util.utcnow())

    cache.path.write_text("not json")
    assert cache.read({}, "parent", "server") is None
