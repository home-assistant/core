"""Fixtures for Google Time Travel tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from google.api_core.exceptions import GatewayTimeout, GoogleAPIError, Unauthorized
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


@pytest.fixture(name="bypass_setup")
def bypass_setup_fixture() -> Generator[None]:
    """Bypass entry setup."""
    with patch(
        "homeassistant.components.google_travel_time.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="bypass_platform_setup")
def bypass_platform_setup_fixture() -> Generator[None]:
    """Bypass platform setup."""
    with patch(
        "homeassistant.components.google_travel_time.sensor.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(name="valid_return")
def valid_return_fixture() -> Generator[AsyncMock]:
    """Return valid API result."""
    client_mock = AsyncMock()
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
    with (
        patch(
            "homeassistant.components.google_travel_time.helpers.RoutesAsyncClient",
            return_value=client_mock,
        ),
        patch(
            "homeassistant.components.google_travel_time.sensor.RoutesAsyncClient",
            return_value=client_mock,
        ),
    ):
        yield client_mock.compute_routes


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(valid_return: AsyncMock) -> None:
    """Return invalid config entry."""
    valid_return.side_effect = GoogleAPIError("test")


@pytest.fixture(name="invalid_api_key")
def invalid_api_key_fixture(valid_return: AsyncMock) -> None:
    """Throw an Unauthorized exception."""
    valid_return.side_effect = Unauthorized("Invalid API key.")


@pytest.fixture(name="timeout")
def timeout_fixture(valid_return: AsyncMock) -> None:
    """Throw a Timeout exception."""
    valid_return.side_effect = GatewayTimeout("Timeout error.")
