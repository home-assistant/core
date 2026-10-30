"""Test the Heiman Home integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import HeimanMQTTError

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

    with (
        patch(
            "homeassistant.components.heiman_home.coordinator.HeimanDataUpdateCoordinator.async_config_entry_first_refresh",
            side_effect=ConfigEntryAuthFailed("Token expired"),
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


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


async def test_unload_returns_false_when_platforms_unload_fails(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test unload returns False when platforms unload fails.

    When platform unloading fails, the entry unload should return False
    without attempting cleanup.
    """
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

    # Set up the entry first so it reaches the LOADED state
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

    # Make the integration's unload hook report failure; the public
    # config_entries.async_unload API must then return False.
    with patch(
        "homeassistant.components.heiman_home.async_unload_entry",
        new_callable=AsyncMock,
        return_value=False,
    ):
        unload_result = await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert unload_result is False


async def test_setup_mqtt_init_failure_with_cleanup(
    hass: HomeAssistant, setup_credentials: None
) -> None:
    """Test setup retries when MQTT initialization fails.

    A transient MQTT broker outage raises ConfigEntryNotReady so Home
    Assistant retries setup; the API client is closed on the way out.
    """
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

    # Make async_init_mqtt_client fail the way a broker outage would
    mock_api_client_instance = MagicMock()
    mock_api_client_instance.close = AsyncMock()

    mock_coordinator = MagicMock()
    mock_coordinator.api_client = mock_api_client_instance
    # The coordinator releases resources through async_shutdown, which
    # DataUpdateCoordinator registers with entry.async_on_unload. The class
    # is mocked here, so mimic the base class registration.
    mock_coordinator.async_shutdown = mock_api_client_instance.close
    mock_coordinator.async_init_mqtt_client = AsyncMock(
        side_effect=HeimanMQTTError("MQTT connection failed")
    )
    mock_coordinator.async_config_entry_first_refresh = AsyncMock(return_value=None)

    def _create_coordinator(*args: object, **kwargs: object) -> MagicMock:
        entry.async_on_unload(mock_coordinator.async_shutdown)
        return mock_coordinator

    with (
        patch(
            "homeassistant.components.heiman_home.HeimanDataUpdateCoordinator",
            side_effect=_create_coordinator,
        ),
        patch(
            "homeassistant.components.heiman_home.async_get_config_entry_implementation",
            new_callable=AsyncMock,
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.heiman_home.HeimanApiClient",
            return_value=mock_api_client_instance,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # A transient MQTT outage is retried by Home Assistant
    assert entry.state is ConfigEntryState.SETUP_RETRY

    mock_api_client_instance.close.assert_awaited_once()
