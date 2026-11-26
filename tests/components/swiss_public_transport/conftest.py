"""Common fixtures for the swiss_public_transport tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_array_fixture

from homeassistant.components.swiss_public_transport.const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_STATIONS,
    CONF_STOPS_AT,
    DOMAIN,
)

START = "Zürich"
DESTINATION = "Bern"
STATIONS = ["Zürich HB"]


@pytest.fixture
def mock_opendata_client() -> Generator[AsyncMock]:
    """Mock a Opendata client."""
    with (
        patch(
            "homeassistant.components.swiss_public_transport.OpendataTransport",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.swiss_public_transport.config_flow.OpendataTransport",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_data.return_value = None
        client.from_name = START
        client.to_name = DESTINATION
        client.connections = load_json_array_fixture("connections.json", DOMAIN)[0:3]
        yield client


@pytest.fixture
def mock_stationboard_client() -> Generator[AsyncMock]:
    """Mock a Opendata stationboard client."""
    with patch(
        "homeassistant.components.swiss_public_transport.OpendataTransportStationboard",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_data.return_value = None
        client.journeys = load_json_array_fixture("departures.json", DOMAIN)
        yield client


@pytest.fixture
def mock_location_client() -> Generator[AsyncMock]:
    """Mock a Opendata location client, which finds a station for each query."""
    with patch(
        "homeassistant.components.swiss_public_transport.config_flow.OpendataTransportLocation",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value
        client.async_get_data.return_value = None
        # Queries which do not return the station they ask for
        client.found = {"zug": [{"name": "Zug"}, {"name": "Zug, Bahnhofplatz"}]}

        def create(session: Any, query: str) -> AsyncMock:
            client.locations = client.found.get(query, [{"name": query}])
            return client

        mock_client.side_effect = create
        yield client


@pytest.fixture
def mock_stationboard_config_entry() -> MockConfigEntry:
    """Mock a stationboard configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATIONS: STATIONS, CONF_STOPS_AT: []},
        title=", ".join(STATIONS),
        unique_id=f"stationboard {', '.join(STATIONS)}",
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94U",
        version=3,
    )


@pytest.fixture(name="swiss_public_transport_config_entry")
def mock_swiss_public_transport_config_entry() -> MockConfigEntry:
    """Mock cookidoo configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_START: START,
            CONF_DESTINATION: DESTINATION,
        },
        title=f"{START} {DESTINATION}",
        entry_id="01JBVVVJ87F6G5V0QJX6HBC94T",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.swiss_public_transport.async_setup_entry",
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry
