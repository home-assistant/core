"""Provide common openAQ fixtures."""
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

from openaq._sync.models.locations import LocationsResponse
from openaq._sync.models.measurements import MeasurementsResponse
import pytest

from homeassistant.components.openAQ.const import API_KEY_ID, DOMAIN, LOCATION_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture

ComponentSetup = Callable[[MockConfigEntry], Awaitable[None]]


class TestingOpenAQ:
    """Mock of openaq client."""

    __test__ = False

    def __init__(self, fixture_locations):
        """Create Mock of openaq client with mocked values."""
        location = LocationsResponse.load(
            load_json_value_fixture(fixture_locations, DOMAIN)
        )
        self.locations = {10496: location}
        self.measurements = self

    def list(self, locations_id, page, limit, date_from):
        """Override list method in openaq library with mocked data."""
        fixture_measurements: str = "measurements.json"

        measurements = MeasurementsResponse.load(
            load_json_value_fixture(fixture_measurements, DOMAIN)
        )
        return measurements


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create openAQ entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="openAQ",
        data={
            API_KEY_ID: "n444fd45sb45uhdss545465ad",
            LOCATION_ID: 10496,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
) -> Callable[[MockConfigEntry], Awaitable[None]]:
    """Fixture for setting up the component."""

    async def func(mock_config_entry: MockConfigEntry) -> None:
        mock_config_entry.add_to_hass(hass)
        with patch(
            "openaq.OpenAQ.__new__", return_value=TestingOpenAQ("location_good.json")
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()

    return func


@pytest.fixture
def mock_aq_client():
    """Fixture to create a basic mock AQClient."""
    with patch("homeassistant.components.openAQ.aq_client.AQClient") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_aq_client_for_config_flow(mock_aq_client):
    """Fixture to provide mocked AQClient with predefined data for config flow tests."""
    # Define standard mocked responses
    mock_aq_client.get_device.side_effect = [
        # Successful data retrieval
        AsyncMock(
            return_value=Mock(
                sensors=[
                    {
                        "type": "pm25",
                        "value": 15,
                        "last_updated": "2023-11-30T12:00:00",
                    },
                    {
                        "type": "pm10",
                        "value": 20,
                        "last_updated": "2023-11-30T12:00:00",
                    },
                ],
                locality="Visby",
            )
        ),
        # Location not found (empty sensors list)
        AsyncMock(return_value=Mock(sensors=[], locality="")),
        # Response for invalid or empty API key: Simulate no sensor data and no locality info
        AsyncMock(return_value=Mock(sensors=[], locality="")),
    ]
    return mock_aq_client
