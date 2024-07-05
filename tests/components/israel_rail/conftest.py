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

INVALID_CONFIG = {"notusername": "israelrail", "notpassword": "test"}

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
        mock_israelrail_api.return_value.query.return_value = [
            TrainRoute(
                [
                    {
                        "orignStation": "3500",
                        "destinationStation": "3700",
                        "departureTime": "2021-10-10T10:10:10",
                        "arrivalTime": "2021-10-10T10:10:10",
                        "originPlatform": "1",
                        "destPlatform": "2",
                        "trainNumber": "1234",
                    }
                ]
            ),
            TrainRoute(
                [
                    {
                        "orignStation": "3500",
                        "destinationStation": "3700",
                        "departureTime": "2021-10-10T10:10:10",
                        "arrivalTime": "2021-10-10T10:10:10",
                        "originPlatform": "1",
                        "destPlatform": "2",
                        "trainNumber": "1234",
                    }
                ]
            ),
            TrainRoute(
                [
                    {
                        "orignStation": "3500",
                        "destinationStation": "3700",
                        "departureTime": "2021-10-10T10:10:10",
                        "arrivalTime": "2021-10-10T10:10:10",
                        "originPlatform": "1",
                        "destPlatform": "2",
                        "trainNumber": "1234",
                    }
                ]
            ),
            TrainRoute(
                [
                    {
                        "orignStation": "3500",
                        "destinationStation": "3700",
                        "departureTime": "2021-10-10T10:10:10",
                        "arrivalTime": "2021-10-10T10:10:10",
                        "originPlatform": "1",
                        "destPlatform": "2",
                        "trainNumber": "1234",
                    }
                ]
            ),
            TrainRoute(
                [
                    {
                        "orignStation": "3500",
                        "destinationStation": "3700",
                        "departureTime": "2021-10-10T10:10:10",
                        "arrivalTime": "2021-10-10T10:10:10",
                        "originPlatform": "1",
                        "destPlatform": "2",
                        "trainNumber": "1234",
                    }
                ]
            ),
        ]

        yield mock_israelrail_api
