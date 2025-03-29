"""Fixtures for Google Time Travel tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from google.api_core.exceptions import GatewayTimeout, GoogleAPIError, Unauthorized
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


@pytest.fixture(name="validate_config_entry")
def validate_config_entry_fixture() -> Generator[AsyncMock]:
    """Return valid config entry."""
    client_mock = AsyncMock()
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
        client_mock.compute_routes.return_value = None
        yield client_mock.compute_routes


@pytest.fixture(name="invalidate_config_entry")
def invalidate_config_entry_fixture(validate_config_entry: AsyncMock) -> None:
    """Return invalid config entry."""
    validate_config_entry.side_effect = GoogleAPIError("test")


@pytest.fixture(name="invalid_api_key")
def invalid_api_key_fixture(validate_config_entry: AsyncMock) -> None:
    """Throw an Unauthorized exception."""
    validate_config_entry.side_effect = Unauthorized("Invalid API key.")


@pytest.fixture(name="timeout")
def timeout_fixture(validate_config_entry: AsyncMock) -> None:
    """Throw a Timeout exception."""
    validate_config_entry.side_effect = GatewayTimeout("Timeout error.")
