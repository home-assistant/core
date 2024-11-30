"""Configuration for Israel rail tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from israelrailapi.api import TrainRoute
import pytest

from homeassistant.components.israel_rail import CONF_DESTINATION, CONF_START, DOMAIN

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_START: "באר יעקב",
    CONF_DESTINATION: "אשקלון",
}

SOURCE_DEST = "באר יעקב אשקלון"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.israel_rail.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=VALID_CONFIG,
        unique_id=SOURCE_DEST,
    )


@pytest.fixture
def mock_israelrail() -> AsyncMock:
    """Build a fixture for the Israel rail API."""
    with (
        patch(
            "homeassistant.components.israel_rail.TrainSchedule",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.israel_rail.config_flow.TrainSchedule",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.query.return_value = TRAINS

        yield client


def get_time(hour: int, minute: int) -> str:
    """Return a time in isoformat."""
    return datetime(2021, 10, 10, hour, minute, 10, tzinfo=ZoneInfo("UTC")).isoformat()


def get_train_route(
    train_number: str = "1234",
    departure_time: str = "2021-10-10T10:10:10",
    arrival_time: str = "2021-10-10T10:10:10",
    origin_platform: str = "1",
    dest_platform: str = "2",
    origin_station: str = "3500",
    destination_station: str = "3700",
) -> TrainRoute:
    """Build a TrainRoute of the israelrail API."""
    return TrainRoute(
        [
            {
                "orignStation": origin_station,
                "destinationStation": destination_station,
                "departureTime": departure_time,
                "arrivalTime": arrival_time,
                "originPlatform": origin_platform,
                "destPlatform": dest_platform,
                "trainNumber": train_number,
            }
        ]
    )


TRAINS = [
    get_train_route(
        train_number="1234",
        departure_time=get_time(10, 10),
        arrival_time=get_time(10, 30),
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1235",
        departure_time=get_time(10, 20),
        arrival_time=get_time(10, 40),
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1236",
        departure_time=get_time(10, 30),
        arrival_time=get_time(10, 50),
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1237",
        departure_time=get_time(10, 40),
        arrival_time=get_time(11, 00),
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1238",
        departure_time=get_time(10, 50),
        arrival_time=get_time(11, 10),
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
]
