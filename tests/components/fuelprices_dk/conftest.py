"""Common fixtures for Fuelprices.dk tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pybraendstofpriser import Flist
import pytest

from homeassistant.components.fuelprices_dk.const import (
    CONF_COMPANY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

TEST_API_KEY = "test-api-key"
TEST_COMPANY = "Circle K"
TEST_STATION = {"id": 1234, "name": "Aarhus C"}
TEST_PRICES = {"Blyfri95": 14.29, "Diesel": 12.99, "Blyfri98": 14.99}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with patch(
        "homeassistant.components.fuelprices_dk.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a standard mock config entry with one station subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Fuelprices.dk",
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title=f"{TEST_COMPANY} - {TEST_STATION['name']}",
                unique_id=f"{TEST_COMPANY}_{TEST_STATION['id']}",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )


@pytest.fixture
def mock_braendstofpriser() -> Generator[AsyncMock]:
    """Mock the pybraendstofpriser client used by the integration."""
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
        client = mock_config_flow_client.return_value
        client.list_companies.return_value = [{"company": TEST_COMPANY}]
        client.list_stations.return_value = Flist([TEST_STATION])
        client.get_prices.return_value = {
            "station": {
                "id": TEST_STATION["id"],
                "name": TEST_STATION["name"],
                "last_update": "2024-01-01T12:00:00",
            },
            "prices": TEST_PRICES,
        }
        yield client
