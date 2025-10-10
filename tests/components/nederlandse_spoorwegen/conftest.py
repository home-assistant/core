"""Fixtures for Nederlandse Spoorwegen tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from ns_api import Station, Trip
import pytest

from homeassistant.components.nederlandse_spoorwegen.const import (
    CONF_FROM,
    CONF_TO,
    CONF_VIA,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_NAME

from .const import API_KEY

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nederlandse_spoorwegen.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nsapi() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with (
        patch(
            "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPI",
            autospec=True,
        ) as mock_nsapi,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.NSAPI",
            new=mock_nsapi,
        ),
    ):
        client = mock_nsapi.return_value
        stations = load_json_object_fixture("stations.json", DOMAIN)
        client.get_stations.return_value = [
            Station(station) for station in stations["payload"]
        ]
        trips = load_json_object_fixture("trip.json", DOMAIN)
        client.get_trips.return_value = [Trip(trip) for trip in trips["trips"]]
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock config entry."""
    return MockConfigEntry(
        title="Nederlandse Spoorwegen",
        data={CONF_API_KEY: API_KEY},
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: "To work",
                    CONF_FROM: "Ams",
                    CONF_TO: "Rot",
                    CONF_VIA: "Ht",
                },
                subentry_type="route",
                title="Test Route",
                unique_id=None,
                subentry_id="01K721DZPMEN39R5DK0ATBMSY8",
            ),
        ],
    )
