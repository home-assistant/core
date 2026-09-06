"""Fixtures for the GeoSphere Austria Warnings tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from pygeosphere_warnings import LocationWarnings
import pytest

from homeassistant.components.geosphere_austria_warnings.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry, load_json_object_fixture

TEST_LATITUDE = 48.2486
TEST_LONGITUDE = 16.3564


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.geosphere_austria_warnings.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_client() -> Generator[AsyncMock]:
    """Mock the GeoSphere Warn API client."""
    with (
        patch(
            "homeassistant.components.geosphere_austria_warnings.coordinator.GeoSphereWarningsClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.geosphere_austria_warnings.config_flow.GeoSphereWarningsClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_last_modified.return_value = datetime(2023, 3, 27, 6, 0, tzinfo=UTC)
        client.get_warnings_for_coords.return_value = LocationWarnings.from_api(
            load_json_object_fixture("get_warnings_for_coords.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Schwechat",
        data={CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE},
        unique_id="30740",
    )
