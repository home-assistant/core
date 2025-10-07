"""Test the Watts Vision integration initialization."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError, ClientResponseError
from visionpluspython import WattsVisionClient
from visionpluspython.auth import WattsVisionAuth

from homeassistant.components.watts import WattsVisionRuntimeData, async_unload_entry
from homeassistant.components.watts.coordinator import WattsVisionCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry

DOMAIN = "watts"
TEST_DEVICE_ID = "test-device-id"
TEST_ACCESS_TOKEN = "test-access-token"
TEST_REFRESH_TOKEN = "test-refresh-token"
TEST_EXPIRES_AT = 9999999999


async def test_setup_entry_success(hass: HomeAssistant) -> None:
    """Test successful setup and unload of entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "device_id": TEST_DEVICE_ID,
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
        patch(
            "homeassistant.components.watts.WattsVisionCoordinator.async_config_entry_first_refresh"
        ) as mock_first_refresh,
        patch("homeassistant.components.watts.WattsVisionClient") as mock_client_class,
        patch("homeassistant.components.watts.WattsVisionAuth") as mock_auth_class,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        mock_session_instance = AsyncMock()
        mock_session_instance.token = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "expires_at": 9999999999,
        }
        mock_session_instance.async_ensure_token_valid = AsyncMock()
        mock_session.return_value = mock_session_instance

        mock_auth_instance = AsyncMock()
        mock_auth_class.return_value = mock_auth_instance

        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        mock_first_refresh.return_value = None

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is True
        assert config_entry.state is ConfigEntryState.LOADED
        mock_first_refresh.assert_called_once()

        # Test unload
        unload_result = await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        assert unload_result is True
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """Test setup with authentication failure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        # Raise 401 error
        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = (
            ClientResponseError(None, None, status=401, message="Unauthorized")
        )
        mock_session_instance.token = {
            "refresh_token": TEST_REFRESH_TOKEN,
            "expires_at": TEST_EXPIRES_AT,
        }
        mock_session.return_value = mock_session_instance

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """Test setup when network is temporarily unavailable."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        mock_session_instance = AsyncMock()
        mock_session_instance.async_ensure_token_valid.side_effect = ClientError(
            "Connection timeout"
        )
        mock_session_instance.token = {
            "refresh_token": TEST_REFRESH_TOKEN,
            "expires_at": TEST_EXPIRES_AT,
        }
        mock_session.return_value = mock_session_instance

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_coordinator_update_failed(hass: HomeAssistant) -> None:
    """Test setup when coordinator update fails."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_at": TEST_EXPIRES_AT,
            },
        },
    )
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
        patch("homeassistant.components.watts.WattsVisionClient") as mock_client_class,
        patch("homeassistant.components.watts.WattsVisionAuth") as mock_auth_class,
        patch(
            "homeassistant.components.watts.WattsVisionCoordinator.async_config_entry_first_refresh"
        ) as mock_first_refresh,
    ):
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        mock_session_instance = AsyncMock()
        mock_session_instance.token = {
            "access_token": TEST_ACCESS_TOKEN,
            "refresh_token": TEST_REFRESH_TOKEN,
            "expires_at": TEST_EXPIRES_AT,
        }
        mock_session_instance.async_ensure_token_valid = AsyncMock()
        mock_session.return_value = mock_session_instance

        mock_auth_instance = AsyncMock()
        mock_auth_class.return_value = mock_auth_instance
        mock_client_instance = AsyncMock()
        mock_client_class.return_value = mock_client_instance

        mock_first_refresh.side_effect = UpdateFailed("Coordinator update failed")

        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert result is False
        assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unload_entry_success(hass: HomeAssistant) -> None:
    """Test successful unload of entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    config_entry.add_to_hass(hass)

    # Mock the runtime data
    mock_client = AsyncMock(spec=WattsVisionClient)
    mock_auth = AsyncMock(spec=WattsVisionAuth)
    mock_coordinator = AsyncMock(spec=WattsVisionCoordinator)

    config_entry.runtime_data = WattsVisionRuntimeData(
        client=mock_client,
        auth=mock_auth,
        coordinator=mock_coordinator,
    )

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ):
        result = await async_unload_entry(hass, config_entry)

        assert result is True


async def test_unload_entry_platform_unload_fails(hass: HomeAssistant) -> None:
    """Test unload when platform unload fails."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
    )
    config_entry.add_to_hass(hass)

    # Mock the runtime data
    mock_client = AsyncMock(spec=WattsVisionClient)
    mock_auth = AsyncMock(spec=WattsVisionAuth)
    mock_coordinator = AsyncMock(spec=WattsVisionCoordinator)

    config_entry.runtime_data = WattsVisionRuntimeData(
        client=mock_client,
        auth=mock_auth,
        coordinator=mock_coordinator,
    )

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await async_unload_entry(hass, config_entry)

        assert result is False
