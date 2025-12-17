"""Test fixtures for the Actron Air Integration."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_actron_api() -> Generator[AsyncMock]:
    """Mock the Actron Air API class."""
    with (
        patch(
            "homeassistant.components.actron_air.ActronAirAPI",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.actron_air.config_flow.ActronAirAPI",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value

        # Mock device code request
        api.request_device_code.return_value = {
            "device_code": "test_device_code",
            "user_code": "ABC123",
            "verification_uri_complete": "https://example.com/device",
            "expires_in": 1800,
        }

        # Mock successful token polling (with a small delay to test progress)
        async def slow_poll_for_token(device_code):
            await asyncio.sleep(0.1)  # Small delay to allow progress state to be tested
            return {
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
            }

        api.poll_for_token = slow_poll_for_token

        # Mock user info
        api.get_user_info = AsyncMock(
            return_value={"id": "test_user_id", "email": "test@example.com"}
        )

        # Mock refresh token property
        api.refresh_token_value = "test_refresh_token"

        # Mock other API methods that might be used
        api.get_systems = AsyncMock(return_value=[])
        api.get_status = AsyncMock(return_value=None)

        yield api


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={CONF_API_TOKEN: "test_refresh_token"},
        unique_id="test_user_id",
    )
