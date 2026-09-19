"""Test Immich Frames cache integrity and invalidation."""

from io import BytesIO
from pathlib import Path

from PIL import Image

from homeassistant.components.immich_frames.cache import FrameCache
from homeassistant.components.immich_frames.const import CONF_SCREEN_SHAPE
from homeassistant.components.immich_frames.rendering import render

from tests.components.immich.const import MOCK_SEARCH_ASSETS


def test_cache_round_trip_and_settings_invalidation(tmp_path: Path) -> None:
    """A cache entry survives a round trip but not a render setting change."""
    cache = FrameCache(tmp_path / "frame.json")
    asset = MOCK_SEARCH_ASSETS[0]

    # Keep the fixture focused on cache behavior while using a valid contract image.
    payload = BytesIO()
    Image.new("RGB", (16, 12), "red").save(payload, "JPEG")
    image, _ = render([payload.getvalue()], "landscape", "show_full")
    options = {CONF_SCREEN_SHAPE: "landscape"}

    cache.write(asset, image, options, "parent")

    assert cache.read(options, "parent") == (asset, image)
    assert cache.read({CONF_SCREEN_SHAPE: "portrait"}, "parent") is None

    cache.clear()
    assert not cache.path.exists()
