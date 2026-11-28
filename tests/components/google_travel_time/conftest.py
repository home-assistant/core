"""Fixtures for Google Maps Travel Time tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from google_maps_routing_api import ComputeRoutesResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.google_travel_time.const import DEFAULT_NAME, DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture(name="mock_config")
async def mock_config_fixture(
    hass: HomeAssistant, data: dict[str, Any], options: dict[str, Any]
) -> MockConfigEntry:
    """Mock a Google Travel Time config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data=data,
        options=options,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return config_entry


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=None,
    ):
        yield


@pytest.fixture
def routes_mock() -> Generator[AsyncMock]:
    """Return valid API result."""
    with patch(
        "homeassistant.components.google_travel_time.helpers.GoogleMapsRoutingApi",
        autospec=True,
    ) as mock_client:
        client_mock = mock_client.return_value
        client_mock.async_compute_routes.return_value = ComputeRoutesResponse.from_dict(
            {
                "routes": [
                    {
                        "distanceMeters": 21300,
                        "duration": "1620s",
                        "localizedValues": {
                            "distance": {"text": "21.3 km"},
                            "duration": {"text": "27 mins"},
                            "staticDuration": {"text": "26 mins"},
                        },
                    }
                ]
            }
        )
        yield client_mock
