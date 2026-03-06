"""Common fixtures for dk_fuelprices tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.dk_fuelprices.const import (
    CONF_COMPANY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_API_KEY = "test-api-key"
TEST_COMPANY = "Circle K"
TEST_STATION = {"id": 1234, "name": "Aarhus C"}
TEST_PRICES = {"Blyfri95": 14.29, "Diesel": 12.99, "Blyfri98": 14.99}


class MockStations(list):
    """Station list helper that mimics pybraendstofpriser find behavior."""

    def find(self, key: str, value: str) -> dict:
        """Find a station by key/value."""
        for station in self:
            if station[key] == value:
                return station
        raise ValueError(f"No station found for {key}={value}")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry for config flow tests."""
    with (
        patch(
            "homeassistant.components.dk_fuelprices.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "homeassistant.components.dk_fuelprices.async_unload_entry",
            return_value=True,
        ),
    ):
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
async def mock_braendstofpriser() -> AsyncGenerator[AsyncMock]:
    """Mock pybraendstofpriser client in both config_flow and api modules."""
    with (
        patch(
            "homeassistant.components.dk_fuelprices.config_flow.Braendstofpriser",
            autospec=True,
        ) as mock_config_flow_client,
        patch(
            "homeassistant.components.dk_fuelprices.coordinator.Braendstofpriser",
            autospec=True,
        ) as mock_api_client,
    ):
        client = mock_config_flow_client.return_value
        client.list_companies.return_value = [{"company": TEST_COMPANY}]
        client.list_stations.return_value = MockStations([TEST_STATION])
        client.get_prices.return_value = {
            "station": {
                "id": TEST_STATION["id"],
                "name": TEST_STATION["name"],
                "last_update": "2024-01-01T12:00:00",
            },
            "prices": TEST_PRICES,
        }

        api_client = mock_api_client.return_value
        api_client.get_prices.return_value = client.get_prices.return_value

        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> MockConfigEntry:
    """Set up the integration from a mock config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
