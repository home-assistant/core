"""Fixtures for the GTFS integration tests."""

from pathlib import Path

import pytest

from homeassistant.core import HomeAssistant

from . import build_feed_zip


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use a temporary config directory for GTFS feeds and databases."""
    return hass_tmp_config_dir


@pytest.fixture(autouse=True)
async def time_zone(hass: HomeAssistant) -> None:
    """Run in the fixture agency's time zone."""
    await hass.config.async_set_time_zone("America/New_York")


@pytest.fixture
def feed_zip() -> bytes:
    """Return the fixture feed as zip bytes."""
    return build_feed_zip()


@pytest.fixture
def feed_file(hass_config_dir: str, feed_zip: bytes) -> Path:
    """Place the fixture feed where the YAML platform reads it."""
    path = Path(hass_config_dir) / "gtfs" / "feed.zip"
    path.parent.mkdir()
    path.write_bytes(feed_zip)
    return path
