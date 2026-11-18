"""Tests for the GTFS integration."""

import io
from pathlib import Path
from typing import Any
import zipfile

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "feed"


def build_feed_zip() -> bytes:
    """Zip the fixture feed."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for path in sorted(FIXTURE_DIR.glob("*.txt")):
            archive.write(path, path.name)
    return buffer.getvalue()


async def setup_yaml_sensor(hass: HomeAssistant, **config: Any) -> None:
    """Set up one legacy YAML GTFS sensor reading feed.zip."""
    assert await async_setup_component(
        hass,
        SENSOR_DOMAIN,
        {SENSOR_DOMAIN: {"platform": "gtfs", "data": "feed.zip", **config}},
    )
    await hass.async_block_till_done()
