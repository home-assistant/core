"""Configuration for GeoJSON Events tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.geo_json_events import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS, CONF_URL

from tests.common import MockConfigEntry

URL = "http://geo.json.local/geo_json_events.json"


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Create a mock GeoJSON Events config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: URL,
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25.0,
        },
        title=f"{URL}, -41.2, 174.7",
        unique_id=f"{URL}, -41.2, 174.7",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock geo_json_events entry setup."""
    with patch(
        "homeassistant.components.geo_json_events.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
