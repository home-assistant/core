"""Test fixtures for the Actron Air Integration."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

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

        # Mock get_ac_systems
        api.get_ac_systems = AsyncMock(
            return_value=[{"serial": "123456", "name": "Test System"}]
        )

        # Mock state manager
        api.state_manager = MagicMock()
        status = api.state_manager.get_status.return_value
        status.master_info.live_temp_c = 22.0
        status.ac_system.system_name = "Test System"
        status.ac_system.serial_number = "123456"
        status.ac_system.master_wc_model = "Test Model"
        status.ac_system.master_wc_firmware_version = "1.0.0"
        status.remote_zone_info = []
        status.min_temp = 16
        status.max_temp = 30
        status.aircon_system.mode = "OFF"
        status.fan_mode = "LOW"
        status.set_point = 24
        status.room_temp = 25
        status.is_on = False

        # Mock user_aircon_settings for the switch platform
        settings = status.user_aircon_settings
        settings.away_mode = False
        settings.continuous_fan_enabled = False
        settings.quiet_mode_enabled = False
        settings.turbo_enabled = False
        settings.turbo_supported = True

        settings.set_away_mode = AsyncMock()
        settings.set_continuous_mode = AsyncMock()
        settings.set_quiet_mode = AsyncMock()
        settings.set_turbo_mode = AsyncMock()

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


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.actron_air.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
