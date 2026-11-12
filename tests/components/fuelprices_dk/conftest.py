"""Common fixtures for Fuelprices.dk tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from pybraendstofpriser import Braendstofpriser, Flist
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_array_fixture

from homeassistant.components.fuelprices_dk.const import (
    CONF_COMPANY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY

TEST_API_KEY = "test-api-key"
TEST_COMPANY = "Circle K"
TEST_STATION = {"id": 1234, "name": "Aarhus C"}
TEST_PRICES = {"Blyfri95": 14.29, "Diesel": 12.99, "Blyfri98": 14.99}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with patch(
        "homeassistant.components.fuelprices_dk.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry(request: pytest.FixtureRequest) -> MockConfigEntry:
    """Create a config entry with station subentries."""
    stations = load_json_array_fixture("bulk_prices.json", DOMAIN)
    return MockConfigEntry(
        domain=DOMAIN,
        title="Fuelprices.dk",
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title=f"{item['company']['company']} - {item['station']['name']}",
                unique_id=f"{item['company']['company']}_{item['station']['id']}",
                data={
                    CONF_COMPANY: item["company"]["company"],
                    CONF_STATION: item["station"],
                },
            )
            for item in stations[: getattr(request, "param", 1)]
        ],
    )


@pytest.fixture
def mock_braendstofpriser_class() -> Generator[MagicMock]:
    """Mock the API client constructor."""
    with (
        patch(
            "homeassistant.components.fuelprices_dk.config_flow.Braendstofpriser",
            autospec=True,
        ) as mock_config_flow_client,
        patch(
            "homeassistant.components.fuelprices_dk.coordinator.Braendstofpriser",
            new=mock_config_flow_client,
        ),
    ):
        yield mock_config_flow_client


@pytest.fixture
def mock_braendstofpriser(
    mock_braendstofpriser_class: MagicMock,
) -> AsyncMock:
    """Return the API client with station and price responses."""
    client = mock_braendstofpriser_class.return_value
    client.list_companies.return_value = [{"company": TEST_COMPANY}]
    client.list_stations.return_value = Flist([TEST_STATION])
    client.get_prices_bulk.return_value = load_json_array_fixture(
        "bulk_prices.json", DOMAIN
    )[:1]
    return client


@pytest.fixture
def mock_other_braendstofpriser() -> MagicMock:
    """Return an API client for a second API key."""
    return create_autospec(Braendstofpriser, instance=True)
