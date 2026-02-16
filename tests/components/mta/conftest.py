"""Test helpers for MTA tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from pymta import Arrival
import pytest

from homeassistant.components.mta.const import CONF_LINE, CONF_STOP_ID, CONF_STOP_NAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain="mta",
        data={
            CONF_LINE: "1",
            CONF_STOP_ID: "127N",
            CONF_STOP_NAME: "Times Sq - 42 St (N direction)",
        },
        unique_id="1_127N",
        entry_id="01J0000000000000000000000",
        title="1 Line - Times Sq - 42 St (N direction)",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.mta.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_subway_feed() -> Generator[MagicMock]:
    """Create a mock SubwayFeed for both coordinator and config flow."""
    # Fixed arrival times: 5, 10, and 15 minutes after test frozen time (2023-10-21 00:00:00 UTC)
    mock_arrivals = [
        Arrival(
            arrival_time=datetime(2023, 10, 21, 0, 5, 0, tzinfo=UTC),
            route_id="1",
            stop_id="127N",
            destination="Van Cortlandt Park - 242 St",
        ),
        Arrival(
            arrival_time=datetime(2023, 10, 21, 0, 10, 0, tzinfo=UTC),
            route_id="1",
            stop_id="127N",
            destination="Van Cortlandt Park - 242 St",
        ),
        Arrival(
            arrival_time=datetime(2023, 10, 21, 0, 15, 0, tzinfo=UTC),
            route_id="1",
            stop_id="127N",
            destination="Van Cortlandt Park - 242 St",
        ),
    ]

    mock_stops = [
        {
            "stop_id": "127N",
            "stop_name": "Times Sq - 42 St",
            "stop_sequence": 1,
        },
        {
            "stop_id": "127S",
            "stop_name": "Times Sq - 42 St",
            "stop_sequence": 2,
        },
    ]

    with (
        patch(
            "homeassistant.components.mta.coordinator.SubwayFeed", autospec=True
        ) as mock_feed,
        patch(
            "homeassistant.components.mta.config_flow.SubwayFeed",
            new=mock_feed,
        ),
    ):
        mock_instance = mock_feed.return_value
        mock_feed.get_feed_id_for_route.return_value = "1"
        mock_instance.get_arrivals.return_value = mock_arrivals
        mock_instance.get_stops.return_value = mock_stops

        yield mock_feed
