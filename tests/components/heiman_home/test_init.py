"""Test the Heiman Home integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.heiman_home import async_migrate_entry
from homeassistant.components.heiman_home.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry

__all__ = [
    "MockConfigEntry",
]


async def test_load_unload_entry(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test loading and unloading a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Test unload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_missing_token(hass: HomeAssistant) -> None:
    """Test setup fails when token is missing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_with_auth_failure(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup with authentication failure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
        side_effect=ConfigEntryAuthFailed("Token expired"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_with_mqtt_disconnect(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload properly disconnects MQTT client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Create mocks for MQTT and API client
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_disconnect = AsyncMock()

    mock_api_client = MagicMock()
    mock_api_client.async_close = AsyncMock()

    mock_coordinator = MagicMock()
    mock_coordinator.mqtt_client = mock_mqtt_client
    mock_coordinator.api_client = mock_api_client

    # Patch the coordinator creation to use our mock
    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Replace runtime_data with our mock after setup
    entry.runtime_data = mock_coordinator

    # Unload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Verify MQTT was disconnected
    mock_mqtt_client.async_disconnect.assert_called_once()
    # Verify API client was closed
    mock_api_client.async_close.assert_called_once()


async def test_setup_entry_oauth2_implementation_unavailable(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup fails when OAuth2 implementation is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.heiman_home.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # When OAuth2 implementation is unavailable, entry should be in SETUP_RETRY state
    # because ConfigEntryNotReady is raised
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_migrate_entry(hass: HomeAssistant, setup_credentials: None) -> None:
    """Test entry migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True


async def test_setup_oauth2_token_reauth_error(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup when OAuth2 token requires re-authentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.OAuth2Session",
            autospec=True,
        ) as mock_oauth_session,
    ):
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=OAuth2TokenRequestReauthError(
                request_info=MagicMock(), domain="heiman"
            )
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_oauth2_token_request_error(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup when OAuth2 token request fails transiently."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.OAuth2Session",
            autospec=True,
        ) as mock_oauth_session,
    ):
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=OAuth2TokenRequestError(
                request_info=MagicMock(), domain="heiman", message="Server error"
            )
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_oauth2_token_value_error(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup when OAuth2 token validation raises ValueError."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.OAuth2Session",
            autospec=True,
        ) as mock_oauth_session,
    ):
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=ValueError("Invalid token format")
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_with_coordinator_none(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload when coordinator is None (e.g., after failed setup)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Simulate failed setup where coordinator is not set
    with patch(
        "homeassistant.components.heiman_home.OAuth2Session",
        autospec=True,
    ) as mock_oauth_session:
        mock_session_instance = MagicMock()
        mock_oauth_session.return_value = mock_session_instance
        mock_session_instance.async_ensure_token_valid = AsyncMock(
            side_effect=Exception("Setup failed")
        )

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    # Entry should be in hass.data even if setup failed
    assert DOMAIN in hass.data

    # Now unload - should handle coordinator being None
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True


async def test_unload_with_mqtt_disconnect_exception(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload handles MQTT disconnect exception gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Create mocks for MQTT client
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_disconnect = AsyncMock(
        side_effect=Exception("MQTT disconnect failed")
    )

    mock_api_client = MagicMock()
    mock_api_client.async_close = AsyncMock()

    mock_coordinator = MagicMock()
    mock_coordinator.mqtt_client = mock_mqtt_client
    mock_coordinator.api_client = mock_api_client

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Replace runtime_data with our mock after setup
    entry.runtime_data = mock_coordinator

    # Unload should handle MQTT disconnect exception gracefully
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True


async def test_unload_with_api_client_close_exception(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload handles API client close exception gracefully."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "test_token",
                "refresh_token": "test_refresh_token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
            "home_id": "test_home",
            "user_id": "test_user",
        },
        unique_id="test_user",
    )
    entry.add_to_hass(hass)

    # Create mocks
    mock_mqtt_client = MagicMock()
    mock_mqtt_client.async_disconnect = AsyncMock()

    mock_api_client = MagicMock()
    mock_api_client.async_close = AsyncMock(side_effect=Exception("API close failed"))

    mock_coordinator = MagicMock()
    mock_coordinator.mqtt_client = mock_mqtt_client
    mock_coordinator.api_client = mock_api_client

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_init_mqtt_client",
            return_value=None,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Replace runtime_data with our mock after setup
    entry.runtime_data = mock_coordinator

    # Unload should handle API close exception gracefully
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert unload_ok is True
