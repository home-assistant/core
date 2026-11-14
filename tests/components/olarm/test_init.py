"""Test the Olarm integration init."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup and unload of entry."""
    config_entry = MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
            "load_zones_bypass_entities": False,
            "auth_implementation": "olarm",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9999999999,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
        patch(
            "homeassistant.components.olarm.OlarmDataUpdateCoordinator.async_config_entry_first_refresh"
        ) as mock_first_refresh,
        patch(
            "homeassistant.components.olarm.mqtt.OlarmFlowClientMQTT.init_mqtt"
        ) as mock_init_mqtt,
        patch(
            "homeassistant.components.olarm.mqtt.OlarmFlowClientMQTT.async_stop"
        ) as mock_stop_mqtt,
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.token = {
            "access_token": "test-access-token",
            "expires_at": 9999999999,
        }
        mock_session.return_value = mock_session_instance

        # Setup entry
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.LOADED
        mock_first_refresh.assert_called_once()
        mock_init_mqtt.assert_called_once()

        # Test unload
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]
        mock_stop_mqtt.assert_called_once()


async def test_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test setup with authentication failure."""
    config_entry = MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
            "auth_implementation": "olarm",
            "token": {
                "access_token": "invalid-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9999999999,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = (
            ClientResponseError(
                request_info=Mock(), history=Mock(), status=401, message="Unauthorized"
            )
        )
        mock_session.return_value = mock_session_instance

        # Setup should raise ConfigEntryAuthFailed
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test setup when network is temporarily unavailable."""
    config_entry = MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
            "auth_implementation": "olarm",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9999999999,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = ClientError(
            "Connection timeout"
        )
        mock_session.return_value = mock_session_instance

        # Setup should raise ConfigEntryNotReady
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failed(hass: HomeAssistant) -> None:
    """Test coordinator update failure."""
    config_entry = MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
            "auth_implementation": "olarm",
            "token": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "expires_at": 9999999999,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
        patch(
            "homeassistant.components.olarm.OlarmDataUpdateCoordinator.async_config_entry_first_refresh"
        ) as mock_first_refresh,
        patch("homeassistant.components.olarm.mqtt.OlarmFlowClientMQTT.init_mqtt"),
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.token = {
            "access_token": "test-access-token",
            "expires_at": 9999999999,
        }
        mock_session.return_value = mock_session_instance

        # Simulate coordinator update failure
        mock_first_refresh.side_effect = UpdateFailed("Coordinator update failed")

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_ERROR
