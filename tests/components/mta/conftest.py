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
        title="1 Line - Times Sq - 42 St (N direction)",
    )


@pytest.fixture
def mock_gtfs_realtime_feed() -> Generator[MagicMock]:
    """Create a mock GTFS-RT feed response."""
    with patch(
        "homeassistant.components.mta.coordinator.SubwayFeed"
    ) as mock_feed_class:
        mock_feed_instance = MagicMock()
        mock_feed_class.return_value = mock_feed_instance
        mock_feed_class.get_feed_id_for_route.return_value = "1"

        arrival_time = datetime.now(UTC).replace(second=0, microsecond=0)
        mock_arrivals = [
            Arrival(
                arrival_time=arrival_time,
                route_id="1",
                stop_id="127N",
                destination="Van Cortlandt Park - 242 St",
            )
        ]

        mock_feed_instance.get_arrivals = AsyncMock(return_value=mock_arrivals)

        yield mock_feed_class


@pytest.fixture
def mock_nyct_feed_config_flow() -> Generator[MagicMock]:
    """Create a mock config flow that uses get_stops()."""
    with patch(
        "homeassistant.components.mta.config_flow.SubwayFeed"
    ) as mock_feed_class:
        mock_feed_class.get_feed_id_for_route.return_value = "1"
        mock_feed_instance = MagicMock()
        mock_feed_instance.get_arrivals = AsyncMock(return_value=[])

        mock_feed_instance.get_stops = AsyncMock(
            return_value=[
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
        )

        mock_feed_class.return_value = mock_feed_instance

        yield mock_feed_class
