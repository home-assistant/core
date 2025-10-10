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
from homeassistant.components.nederlandse_spoorwegen.coordinator import (
    NSDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import (
    API_KEY,
    INTEGRATION_TITLE,
    SUBENTRY_ID_1,
    SUBENTRY_ID_2,
    SUBENTRY_TYPE_ROUTE,
    TEST_ROUTE_TITLE_1,
    TEST_ROUTE_TITLE_2,
)

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
            "homeassistant.components.nederlandse_spoorwegen.coordinator.NSAPI",
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
        title=INTEGRATION_TITLE,
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
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title="Test Route",
                unique_id=None,
                subentry_id=SUBENTRY_ID_1,
            ),
        ],
    )


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_nsapi
) -> NSDataUpdateCoordinator:
    """Return a coordinator instance using existing mock_config_entry fixture."""
    # Use the route data from the existing mock_config_entry
    subentry = list(mock_config_entry.subentries.values())[0]
    return NSDataUpdateCoordinator(
        hass=hass,
        config_entry=mock_config_entry,
        route_id=subentry.subentry_id,
        route_data=dict(subentry.data),
    )


@pytest.fixture
def mock_config_entry_with_multiple_routes() -> MockConfigEntry:
    """Mock config entry with multiple routes using existing patterns."""
    return MockConfigEntry(
        title=INTEGRATION_TITLE,
        data={CONF_API_KEY: API_KEY},
        domain=DOMAIN,
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: TEST_ROUTE_TITLE_1,
                    CONF_FROM: "Ams",
                    CONF_TO: "Rot",
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=TEST_ROUTE_TITLE_1,
                unique_id=None,
                subentry_id=SUBENTRY_ID_1,
            ),
            ConfigSubentryDataWithId(
                data={
                    CONF_NAME: TEST_ROUTE_TITLE_2,
                    CONF_FROM: "Hag",
                    CONF_TO: "Utr",
                },
                subentry_type=SUBENTRY_TYPE_ROUTE,
                title=TEST_ROUTE_TITLE_2,
                unique_id=None,
                subentry_id=SUBENTRY_ID_2,
            ),
        ],
    )
