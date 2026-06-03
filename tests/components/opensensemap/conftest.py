"""Common fixtures for the openSenseMap tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.opensensemap.const import CONF_STATION_ID, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_json_object_fixture

TEST_STATION_ID = "test-station-id"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry to avoid real setup during config flow tests."""
    with patch(
        "homeassistant.components.opensensemap.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def station_data(hass: HomeAssistant) -> dict:
    """Load the example station data."""
    return await async_load_json_object_fixture(hass, "station.json", DOMAIN)


@pytest.fixture
async def mock_opensensemap_api(
    station_data: dict,
) -> AsyncGenerator[AsyncMock]:
    """Mock the OpenSenseMap API client."""
    with (
        patch(
            "homeassistant.components.opensensemap.OpenSenseMap",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.opensensemap.config_flow.OpenSenseMap",
            new=mock_client,
        ),
    ):
        instance = mock_client.return_value
        instance.data = station_data
        sensor_values = {
            sensor["title"]: float(sensor["lastMeasurement"]["value"])
            for sensor in station_data["sensors"]
        }
        instance.pm2_5 = sensor_values.get("PM2.5")
        instance.pm10 = sensor_values.get("PM10")
        yield instance


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Station",
        unique_id=TEST_STATION_ID,
        data={CONF_STATION_ID: TEST_STATION_ID},
    )
