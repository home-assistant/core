"""Configure tests for the mvglive integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.mvglive.const import (
    CONF_STATION_ID,
    CONF_STATION_NAME,
    DOMAIN,
)

from tests.common import MockConfigEntry

TEST_STATION = {"id": "de:09162:6", "name": "Hauptbahnhof", "place": "München"}

TEST_STATIONS = [
    TEST_STATION,
    {"id": "de:09162:2", "name": "Marienplatz", "place": "München"},
]

TEST_DEPARTURES = [
    {
        "destination": "Feldmoching",
        "line": "U2",
        "type": "U-Bahn",
        "cancelled": False,
        "icon": "mdi:subway",
        "platform": "1",
        "time": 32503683600,
    }
]


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.mvglive.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create an mvglive entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TEST_STATION["name"],
        unique_id=TEST_STATION["id"],
        data={
            CONF_STATION_ID: TEST_STATION["id"],
            CONF_STATION_NAME: TEST_STATION["name"],
        },
    )


@pytest.fixture
def mvg_api() -> Generator[dict[str, AsyncMock]]:
    """Mock the mvg.MvgApi calls used by the config flow and sensor."""
    with (
        patch(
            "homeassistant.components.mvglive.config_flow.MvgApi.stations_async",
            AsyncMock(return_value=TEST_STATIONS),
        ) as stations_async,
        patch(
            "homeassistant.components.mvglive.config_flow.MvgApi.station_async",
            AsyncMock(return_value=TEST_STATION),
        ) as station_async,
        patch(
            "homeassistant.components.mvglive.sensor.MvgApi.departures_async",
            AsyncMock(return_value=TEST_DEPARTURES),
        ) as departures_async,
    ):
        yield {
            "stations_async": stations_async,
            "station_async": station_async,
            "departures_async": departures_async,
        }
