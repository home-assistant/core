"""Tests for the GTFS integration."""

from collections.abc import Mapping
import io
from pathlib import Path
from typing import Any
import zipfile

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gtfs.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "feed"

FEED_URL = "https://example.com/gtfs.zip"
TEST_DATABASE = "test_feed.sqlite"
ROUTE_SUBENTRY_ID = "route_s1_s3"
ROUTE_ENTITY_ID = "calendar.first_street_to_third_street"


def build_feed_zip(
    exclude: frozenset[str] = frozenset(),
    replace: Mapping[str, str | bytes] | None = None,
) -> bytes:
    """Zip the fixture feed, optionally leaving files out or replacing them."""
    replace = replace or {}
    paths = sorted(FIXTURE_DIR.glob("*.txt"))
    assert set(replace) <= {path.name for path in paths}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in paths:
            if path.name not in exclude:
                archive.writestr(path.name, replace.get(path.name, path.read_bytes()))
    return buffer.getvalue()


def gtfs_files(hass: HomeAssistant) -> list[str]:
    """Return the names of the files in the GTFS cache folder."""
    return sorted(path.name for path in Path(hass.config.cache_path(DOMAIN)).glob("*"))


async def setup_yaml_sensor(hass: HomeAssistant, **config: Any) -> None:
    """Set up one legacy YAML GTFS sensor reading feed.zip."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": "gtfs", "data": "feed.zip", **config}},
    )
    await hass.async_block_till_done()


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the GTFS integration for a config entry."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
