"""Provide common openAQ fixtures."""
from collections.abc import Awaitable, Callable
from unittest.mock import patch

from openaq._sync.models.locations import LocationsResponse
from openaq._sync.models.measurements import MeasurementsResponse
import pytest

from homeassistant.components.openAQ.const import API_KEY_ID, DOMAIN, LOCATION_ID
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_json_value_fixture

ComponentSetup = Callable[[MockConfigEntry], Awaitable[None]]


class MockAQClient:
    """Mock for AQClient that simulates a successful response."""

    def __init__(self, devices):
        """Initialize the mock AQClient."""
        self.devices = devices

    def get_device(self):
        """Simulate getting device data from AQClient."""
        return self.devices


class OpenAQMock:
    """Mock of openaq client."""

    def __init__(self, fixture_locations, fixture_measurements):
        """Create Mock of openaq client with mocked values."""
        location = LocationsResponse.load(
            load_json_value_fixture(fixture_locations, DOMAIN)
        )
        self.locations = {10496: location}
        self.fixture_measurements = fixture_measurements
        self.measurements = self

    def list(self, locations_id, page, limit, date_from):
        """Override list method in openaq library with mocked data."""
        # fixture_measurements: str = "measurements_good.json"

        measurements = MeasurementsResponse.load(
            load_json_value_fixture(self.fixture_measurements, DOMAIN)
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

    async def func(
        mock_config_entry: MockConfigEntry, location: str, fixture_measurements
    ) -> None:
        mock_config_entry.add_to_hass(hass)
        with patch(
            "openaq.OpenAQ.__new__",
            return_value=OpenAQMock(location, fixture_measurements),
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()

    return func
