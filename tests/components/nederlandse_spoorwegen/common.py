"""Common test utilities for Nederlandse Spoorwegen."""

from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from homeassistant.components.nederlandse_spoorwegen.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_API_KEY = "test_api_key_123"

TEST_CONFIG = {
    CONF_API_KEY: TEST_API_KEY,
}

TEST_CONFIG_WITH_ROUTES = {
    CONF_API_KEY: TEST_API_KEY,
    "routes": [
        {
            CONF_NAME: "Amsterdam to Utrecht",
            "from": "AMF",
            "to": "UT",
        },
        {
            CONF_NAME: "Utrecht to Den Haag",
            "from": "UT",
            "to": "GV",
            "via": "AD",
        },
    ],
}


def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG,
        title="Nederlandse Spoorwegen",
        unique_id=DOMAIN,
    )


def mock_config_entry_with_routes() -> MockConfigEntry:
    """Return a mocked config entry with routes."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=TEST_CONFIG_WITH_ROUTES,
        title="Nederlandse Spoorwegen",
        unique_id=DOMAIN,
    )


class MockTrip:
    """Mock trip object."""

    def __init__(
        self,
        departure_time_planned=None,
        departure_time_actual=None,
        departure_platform_planned=None,
        departure_platform_actual=None,
        going=None,
        status=None,
    ) -> None:
        """Initialize mock trip."""
        self.departure_time_planned = departure_time_planned
        self.departure_time_actual = departure_time_actual
        self.departure_platform_planned = departure_platform_planned
        self.departure_platform_actual = departure_platform_actual
        self.going = going
        self.status = status


@contextmanager
def mock_nsapi_wrapper():
    """Return a mocked NSAPIWrapper."""
    with (
        patch(
            "homeassistant.components.nederlandse_spoorwegen.coordinator.NSAPIWrapper"
        ) as mock_coordinator_api,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.config_flow.NSAPIWrapper"
        ) as mock_config_api,
        patch(
            "homeassistant.components.nederlandse_spoorwegen.api.NSAPIWrapper"
        ) as mock_init_api,
    ):
        # Mock the NSAPIWrapper class for coordinator
        mock_coordinator_instance = AsyncMock()
        mock_coordinator_api.return_value = mock_coordinator_instance

        # Mock the NSAPIWrapper class for config flow
        mock_config_instance = AsyncMock()
        mock_config_api.return_value = mock_config_instance

        # Mock the NSAPIWrapper class for init
        mock_init_instance = AsyncMock()
        mock_init_api.return_value = mock_init_instance

        # Mock some default trips
        mock_trip1 = MockTrip(
            departure_time_planned=datetime(2025, 1, 1, 14, 30, tzinfo=UTC),
            departure_time_actual=datetime(2025, 1, 1, 14, 32, tzinfo=UTC),
            departure_platform_planned="5a",
            departure_platform_actual="5a",
            going="Utrecht Centraal",
            status="ON_TIME",
        )

        mock_trip2 = MockTrip(
            departure_time_planned=datetime(2025, 1, 1, 15, 0, tzinfo=UTC),
            departure_time_actual=datetime(2025, 1, 1, 15, 0, tzinfo=UTC),
            departure_platform_planned="5a",
            departure_platform_actual="5a",
            going="Utrecht Centraal",
            status="ON_TIME",
        )

        mock_coordinator_instance.get_trips.return_value = [mock_trip1, mock_trip2]
        mock_coordinator_instance.validate_api_key.return_value = True
        mock_coordinator_instance.get_stations.return_value = []

        mock_config_instance.validate_api_key.return_value = True
        mock_config_instance.get_stations.return_value = []

        mock_init_instance.validate_api_key.return_value = True
        mock_init_instance.get_stations.return_value = []

        yield mock_coordinator_instance


# Backward compatibility alias
mock_nsapi = mock_nsapi_wrapper


async def init_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the Nederlandse Spoorwegen integration for testing."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
