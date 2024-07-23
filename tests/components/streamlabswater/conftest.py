"""Common fixtures for the StreamLabs tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from streamlabswater.streamlabswater import StreamlabsClient

from homeassistant.components.streamlabswater import DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.streamlabswater.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock StreamLabs config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="StreamLabs",
        data={CONF_API_KEY: "abc"},
    )


@pytest.fixture(name="streamlabswater")
def mock_streamlabswater() -> Generator[AsyncMock, None, None]:
    """Mock the StreamLabs client."""

    locations = load_json_object_fixture("streamlabswater/get_locations.json")

    water_usage = load_json_object_fixture("streamlabswater/water_usage.json")

    mock = AsyncMock(spec=StreamlabsClient)
    mock.get_locations.return_value = locations
    mock.get_water_usage_summary.return_value = water_usage

    with patch(
        "homeassistant.components.streamlabswater.StreamlabsClient",
        return_value=mock,
    ) as mock_client:
        yield mock_client
