"""Test the Olarm integration init."""

from unittest.mock import AsyncMock, patch

from olarmflowclient import OlarmFlowClientApiError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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
            "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.get_device"
        ) as mock_get_device,
        patch(
            "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.init_mqtt"
        ) as mock_init_mqtt,
        # patch(
        #     "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        # ) as mock_impl,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
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
        mock_get_device.assert_called_once()
        mock_init_mqtt.assert_called_once()

        # Test unload
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Ignore mypy false-positive on state comparison overlap
        assert config_entry.state is ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]


async def test_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test setup with authentication failure."""
    config_entry = MockConfigEntry(
        domain="olarm",
        data={
            "user_id": "test-user-id",
            "device_id": "test-device-id",
            "load_zones_bypass_entities": False,
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
            "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.get_device"
        ) as mock_get_device,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
        # Prevent reauth flow from starting during test
        patch("homeassistant.config_entries.ConfigEntry.async_start_reauth"),
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.token = {
            "access_token": "invalid-token",
            "expires_at": 9999999999,
        }
        mock_session.return_value = mock_session_instance

        # Simulate API auth error
        mock_get_device.side_effect = OlarmFlowClientApiError("401 Unauthorized")

        # Setup should complete but entry should be in setup_error state
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # The entry should be in an error state due to auth failure
        assert config_entry.state.name in ["SETUP_ERROR", "SETUP_RETRY"]


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test setup when API is temporarily unavailable."""
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
            "homeassistant.components.olarm.coordinator.OlarmFlowClientCoordinator.get_device"
        ) as mock_get_device,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ),
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_session_instance = AsyncMock()
        mock_session_instance.token = {
            "access_token": "test-access-token",
            "expires_at": 9999999999,
        }
        mock_session.return_value = mock_session_instance

        # Simulate network error
        mock_get_device.side_effect = OlarmFlowClientApiError("Connection timeout")

        # Setup should complete but config entry should be in setup_retry state
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # The entry should be in setup_retry state due to temporary failure
        assert config_entry.state.name == "SETUP_RETRY"
