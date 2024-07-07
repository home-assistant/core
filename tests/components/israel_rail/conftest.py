"""Configuration for 17Track tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from israelrailapi.api import TrainRoute
import pytest
from typing_extensions import Generator

from homeassistant.components.israel_rail import CONF_DESTINATION, CONF_START, DOMAIN

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_START: "start",
    CONF_DESTINATION: "destination",
}

SOURCE_DEST = "Source1 Destination1"


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
def mock_israelrail():
    """Build a fixture for the 17Track API."""
    mock_israelrail_api = MagicMock()
    with (
        patch(
            "homeassistant.components.israel_rail.TrainSchedule",
            return_value=mock_israelrail_api,
        ),
        patch(
            "homeassistant.components.israel_rail.coordinator.TrainSchedule",
            return_value=mock_israelrail_api,
        ),
        patch(
            "homeassistant.components.israel_rail.config_flow.TrainSchedule",
            return_value=mock_israelrail_api,
        ) as mock_israelrail_api,
    ):
        mock_israelrail_api.return_value.query.return_value = trains[:]

        yield mock_israelrail_api


def get_train_route(
    train_number: str = "1234",
    departure_time: str = "2021-10-10T10:10:10",
    arrival_time: str = "2021-10-10T10:10:10",
    origin_platform: str = "1",
    dest_platform: str = "2",
    origin_station: str = "3500",
    destination_station: str = "3700",
):
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


trains = [
    get_train_route(
        train_number="1234",
        departure_time="2021-10-10T10:10:10",
        arrival_time="2021-10-10T10:30:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1235",
        departure_time="2021-10-10T10:20:10",
        arrival_time="2021-10-10T10:40:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1236",
        departure_time="2021-10-10T10:30:10",
        arrival_time="2021-10-10T10:50:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1237",
        departure_time="2021-10-10T10:40:10",
        arrival_time="2021-10-10T11:00:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1238",
        departure_time="2021-10-10T10:50:10",
        arrival_time="2021-10-10T11:10:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
]

trains_wrong_format = [
    get_train_route(
        train_number="1234",
        departure_time="2021-10-1010:10:10",
        arrival_time="2021-10-10T10:30:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1235",
        departure_time="2021-10-1010:20:10",
        arrival_time="2021-10-10T10:40:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1236",
        departure_time="2021-10-1010:30:10",
        arrival_time="2021-10-10T10:50:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1237",
        departure_time="2021-10-1010:40:10",
        arrival_time="2021-10-10T11:00:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
    get_train_route(
        train_number="1238",
        departure_time="2021-10-1010:50:10",
        arrival_time="2021-10-10T11:10:10",
        origin_platform="1",
        dest_platform="2",
        origin_station="3500",
        destination_station="3700",
    ),
]
