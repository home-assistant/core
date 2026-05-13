"""Test helpers for MTA tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from pymta import Arrival
import pytest

from homeassistant.components.mta.const import (
    CONF_LINE,
    CONF_ROUTE,
    CONF_STOP_ID,
    CONF_STOP_NAME,
    DOMAIN,
    SUBENTRY_TYPE_BUS,
    SUBENTRY_TYPE_SUBWAY,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

MOCK_SUBWAY_ARRIVALS = [
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

MOCK_SUBWAY_STOPS = [
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

MOCK_BUS_ARRIVALS = [
    Arrival(
        arrival_time=datetime(2023, 10, 21, 0, 5, 0, tzinfo=UTC),
        route_id="M15",
        stop_id="400561",
        destination="South Ferry",
    ),
    Arrival(
        arrival_time=datetime(2023, 10, 21, 0, 12, 0, tzinfo=UTC),
        route_id="M15",
        stop_id="400561",
        destination="South Ferry",
    ),
    Arrival(
        arrival_time=datetime(2023, 10, 21, 0, 20, 0, tzinfo=UTC),
        route_id="M15",
        stop_id="400561",
        destination="South Ferry",
    ),
]

MOCK_BUS_STOPS = [
    {
        "stop_id": "400561",
        "stop_name": "1 Av/E 79 St",
        "stop_sequence": 1,
    },
    {
        "stop_id": "400562",
        "stop_name": "1 Av/E 72 St",
        "stop_sequence": 2,
    },
]

# Bus stops with direction info (from updated library)
MOCK_BUS_STOPS_WITH_DIRECTION = [
    {
        "stop_id": "400561",
        "stop_name": "1 Av/E 79 St",
        "stop_sequence": 1,
        "direction_id": 0,
        "direction_name": "South Ferry",
    },
    {
        "stop_id": "400570",
        "stop_name": "1 Av/E 79 St",
        "stop_sequence": 15,
        "direction_id": 1,
        "direction_name": "Harlem",
    },
    {
        "stop_id": "400562",
        "stop_name": "1 Av/E 72 St",
        "stop_sequence": 2,
        "direction_id": 0,
        "direction_name": "South Ferry",
    },
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry (main entry without subentries)."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: None},
        version=1,
        minor_version=1,
        entry_id="01J0000000000000000000000",
        title="MTA",
    )


@pytest.fixture
def mock_config_entry_with_api_key() -> MockConfigEntry:
    """Return a mock config entry with API key."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key"},
        version=1,
        minor_version=1,
        entry_id="01J0000000000000000000001",
        title="MTA",
    )


@pytest.fixture
def mock_subway_subentry() -> ConfigSubentry:
    """Return a mock subway subentry."""
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_LINE: "1",
                CONF_STOP_ID: "127N",
                CONF_STOP_NAME: "Times Sq - 42 St (N direction)",
            }
        ),
        subentry_id="01JSUBWAY00000000000000001",
        subentry_type=SUBENTRY_TYPE_SUBWAY,
        title="1 - Times Sq - 42 St (N direction)",
        unique_id="1_127N",
    )


@pytest.fixture
def mock_bus_subentry() -> ConfigSubentry:
    """Return a mock bus subentry."""
    return ConfigSubentry(
        data=MappingProxyType(
            {
                CONF_ROUTE: "M15",
                CONF_STOP_ID: "400561",
                CONF_STOP_NAME: "1 Av/E 79 St",
            }
        ),
        subentry_id="01JBUS0000000000000000001",
        subentry_type=SUBENTRY_TYPE_BUS,
        title="M15 - 1 Av/E 79 St",
        unique_id="bus_M15_400561",
    )


@pytest.fixture
def mock_config_entry_with_subway_subentry(
    mock_config_entry: MockConfigEntry,
    mock_subway_subentry: ConfigSubentry,
) -> MockConfigEntry:
    """Return a mock config entry with a subway subentry."""
    mock_config_entry.subentries = {
        mock_subway_subentry.subentry_id: mock_subway_subentry
    }
    return mock_config_entry


@pytest.fixture
def mock_config_entry_with_bus_subentry(
    mock_config_entry_with_api_key: MockConfigEntry,
    mock_bus_subentry: ConfigSubentry,
) -> MockConfigEntry:
    """Return a mock config entry with a bus subentry."""
    mock_config_entry_with_api_key.subentries = {
        mock_bus_subentry.subentry_id: mock_bus_subentry
    }
    return mock_config_entry_with_api_key


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
        mock_instance.get_arrivals.return_value = MOCK_SUBWAY_ARRIVALS
        mock_instance.get_stops.return_value = MOCK_SUBWAY_STOPS

        yield mock_feed


@pytest.fixture
def mock_bus_feed() -> Generator[MagicMock]:
    """Create a mock BusFeed for both coordinator and config flow."""
    with (
        patch(
            "homeassistant.components.mta.coordinator.BusFeed", autospec=True
        ) as mock_feed,
        patch(
            "homeassistant.components.mta.config_flow.BusFeed",
            new=mock_feed,
        ),
    ):
        mock_instance = mock_feed.return_value
        mock_instance.get_arrivals.return_value = MOCK_BUS_ARRIVALS
        mock_instance.get_stops.return_value = MOCK_BUS_STOPS

        yield mock_feed


@pytest.fixture
def mock_bus_feed_with_direction() -> Generator[MagicMock]:
    """Create a mock BusFeed with direction info."""
    with (
        patch(
            "homeassistant.components.mta.coordinator.BusFeed", autospec=True
        ) as mock_feed,
        patch(
            "homeassistant.components.mta.config_flow.BusFeed",
            new=mock_feed,
        ),
    ):
        mock_instance = mock_feed.return_value
        mock_instance.get_arrivals.return_value = MOCK_BUS_ARRIVALS
        mock_instance.get_stops.return_value = MOCK_BUS_STOPS_WITH_DIRECTION

        yield mock_feed
