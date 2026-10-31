"""Fixtures for the GTFS integration tests."""

from collections.abc import Generator
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.gtfs.const import (
    CONF_DATABASE,
    CONF_DESTINATION,
    CONF_ORIGIN,
    DOMAIN,
    SUBENTRY_TYPE_ROUTE,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from . import FEED_URL, ROUTE_SUBENTRY_ID, TEST_DATABASE, build_feed_zip


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


@pytest.fixture
def mock_feed_download(
    aioclient_mock: AiohttpClientMocker, feed_zip: bytes
) -> AiohttpClientMocker:
    """Serve the fixture feed at FEED_URL."""
    aioclient_mock.get(FEED_URL, content=feed_zip)
    return aioclient_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Skip entry setup in flow tests."""
    with patch(
        "homeassistant.components.gtfs.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a feed entry with one First Street to Third Street route."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Agency",
        data={CONF_URL: FEED_URL, CONF_DATABASE: TEST_DATABASE},
        subentries_data=[
            ConfigSubentryDataWithId(
                data={CONF_ORIGIN: "S1", CONF_DESTINATION: "S3"},
                subentry_id=ROUTE_SUBENTRY_ID,
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title="First Street to Third Street",
                unique_id=json.dumps(["S1", "S3"]),
            )
        ],
    )
