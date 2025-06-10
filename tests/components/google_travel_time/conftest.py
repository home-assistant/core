"""Fixtures for Google Time Travel tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from google.maps.routing_v2 import ComputeRoutesResponse, Route
from google.protobuf import duration_pb2
from google.type import localized_text_pb2
import pytest

from homeassistant.components.google_travel_time.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_config")
async def mock_config_fixture(
    hass: HomeAssistant, data: dict[str, Any], options: dict[str, Any]
) -> MockConfigEntry:
    """Mock a Google Travel Time config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
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
        return_value=True,
    ):
        yield


@pytest.fixture
def routes_mock() -> Generator[AsyncMock]:
    """Return valid API result."""
    with (
        patch(
            "homeassistant.components.google_travel_time.helpers.RoutesAsyncClient",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.google_travel_time.sensor.RoutesAsyncClient",
            new=mock_client,
        ),
    ):
        client_mock = mock_client.return_value
        client_mock.compute_routes.return_value = ComputeRoutesResponse(
            mapping={
                "routes": [
                    Route(
                        mapping={
                            "localized_values": Route.RouteLocalizedValues(
                                mapping={
                                    "distance": localized_text_pb2.LocalizedText(
                                        text="21.3 km"
                                    ),
                                    "duration": localized_text_pb2.LocalizedText(
                                        text="27 mins"
                                    ),
                                    "static_duration": localized_text_pb2.LocalizedText(
                                        text="26 mins"
                                    ),
                                }
                            ),
                            "duration": duration_pb2.Duration(seconds=1620),
                        }
                    )
                ]
            }
        )
        yield client_mock
