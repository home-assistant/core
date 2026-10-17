"""Test fixtures for the Actron Air Integration."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from actron_neo_api.models.auth import ActronAirDeviceCode, ActronAirUserInfo
from actron_neo_api.models.settings import ActronAirUserAirconSettings
from actron_neo_api.models.status import ActronAirStatus
from actron_neo_api.models.system import ActronAirACSystem, ActronAirSystemInfo
import pytest

from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_actron_api_class() -> Generator[MagicMock]:
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
        yield mock_api


@pytest.fixture
def mock_actron_api(mock_actron_api_class: MagicMock) -> Generator[AsyncMock]:
    """Mock the Actron Air API instance."""
    with (
        patch.object(ActronAirACSystem, "set_system_mode", new_callable=AsyncMock),
        patch.object(
            ActronAirUserAirconSettings, "set_away_mode", new_callable=AsyncMock
        ),
        patch.object(
            ActronAirUserAirconSettings,
            "set_continuous_mode",
            new_callable=AsyncMock,
        ),
        patch.object(
            ActronAirUserAirconSettings, "set_quiet_mode", new_callable=AsyncMock
        ),
        patch.object(
            ActronAirUserAirconSettings, "set_turbo_mode", new_callable=AsyncMock
        ),
        patch.object(
            ActronAirUserAirconSettings, "set_temperature", new_callable=AsyncMock
        ),
        patch.object(
            ActronAirUserAirconSettings, "set_fan_mode", new_callable=AsyncMock
        ),
    ):
        api = mock_actron_api_class.return_value

        # Mock device code request
        api.request_device_code.return_value = ActronAirDeviceCode(
            device_code="test_device_code",
            user_code="ABC123",
            verification_uri="https://example.com",
            verification_uri_complete="https://example.com/device",
            expires_in=1800,
            interval=5,
        )

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
            return_value=ActronAirUserInfo(id="test_user_id", email="test@example.com")
        )

        # Mock refresh token property
        api.refresh_token_value = "test_refresh_token"

        # Mock get_ac_systems
        api.get_ac_systems = AsyncMock(
            return_value=[ActronAirSystemInfo(serial="123456")]
        )

        # Mock realtime push
        api.start_push = AsyncMock(return_value=True)
        api.stop_push = AsyncMock()
        api.subscribe_system_updates = MagicMock(return_value=MagicMock())
        api.subscribe_connection_state = MagicMock(return_value=MagicMock())

        # Build status from fixture JSON
        status = ActronAirStatus.model_validate(
            load_json_object_fixture("status.json", DOMAIN)
        )
        status.set_api(api)

        # Mock state manager to return our real pydantic status
        api.state_manager = MagicMock()
        api.state_manager.get_status.return_value = status

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
def mock_zone() -> MagicMock:
    """Return a mocked zone."""
    zone = MagicMock()
    zone.exists = True
    zone.zone_id = 0
    zone.zone_name = "Test Zone"
    zone.title = "Living Room"
    zone.live_temp_c = 22.0
    zone.current_setpoint = 24.0
    zone.is_active = True
    zone.zone_position = 75.0
    zone.hvac_mode = "COOL"
    zone.humidity = 50.0
    zone.min_temp = 16
    zone.max_temp = 30
    zone.set_temperature = AsyncMock()
    zone.enable = AsyncMock()
    return zone


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock async_setup_entry."""
    with patch(
        "homeassistant.components.actron_air.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration_with_zone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_actron_api: AsyncMock,
    mock_zone: MagicMock,
) -> None:
    """Set up the Actron Air integration with zone for testing."""
    status = mock_actron_api.state_manager.get_status.return_value
    status.remote_zone_info = [mock_zone]

    with patch("homeassistant.components.actron_air.PLATFORMS", [Platform.CLIMATE]):
        await setup_integration(hass, mock_config_entry)
