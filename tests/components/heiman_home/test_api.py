"""Tests for the Heiman Home API client."""

from unittest.mock import AsyncMock, MagicMock, patch

from heimanconnect import HeimanAuthError, HeimanConnectionError
import pytest

from homeassistant.components.heiman_home.api import HeimanApiClient
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def mock_oauth_session():
    """Create a mock OAuth session."""
    session = MagicMock(spec=OAuth2Session)
    session.token = {"access_token": "test-token"}
    session.async_ensure_token_valid = AsyncMock()
    return session


async def test_api_client_initialization(hass: HomeAssistant) -> None:
    """Test API client initialization."""
    client = HeimanApiClient(hass, token_data={"access_token": "test-token"})

    assert client.hass == hass
    assert client._get_access_token() == "test-token"


async def test_api_client_no_token(hass: HomeAssistant) -> None:
    """Test API client with no token."""
    client = HeimanApiClient(hass)

    assert client._get_access_token() is None


async def test_async_get_user_info_success(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test getting user info successfully."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    mock_user = MagicMock()
    mock_user.user_id = "test-user-id"
    mock_user.email = "test@example.com"

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_user_info = AsyncMock(return_value=mock_user)

        user = await client.async_get_user_info()

        assert user == mock_user
        mock_oauth_session.async_ensure_token_valid.assert_called_once()


async def test_async_get_user_info_auth_failed(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test getting user info with authentication failure."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_user_info = AsyncMock(
            side_effect=HeimanAuthError("Auth failed")
        )

        with pytest.raises(ConfigEntryAuthFailed):
            await client.async_get_user_info()


async def test_async_get_homes_success(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test getting homes list successfully."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    mock_home = MagicMock()
    mock_home.home_id = "home-1"
    mock_home.home_name = "Test Home"

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_homes = AsyncMock(return_value=[mock_home])

        homes = await client.async_get_homes()

        assert len(homes) == 1
        assert homes[0] == mock_home


async def test_async_get_devices_success(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test getting devices successfully."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    mock_device = MagicMock()
    mock_device.device_id = "device-1"
    mock_device.device_name = "Test Device"

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_devices = AsyncMock(
            return_value={"device-1": mock_device}
        )

        devices = await client.async_get_devices(home_id="home-1")

        assert len(devices) == 1
        assert "device-1" in devices
        assert devices["device-1"] == mock_device


async def test_async_get_device_properties_success(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test getting device properties successfully."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    mock_properties = {
        "temperature": 25.0,
        "humidity": 60.0,
    }

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_device_properties = AsyncMock(
            return_value=mock_properties
        )

        properties = await client.async_get_device_properties("device-1")

        assert properties == mock_properties


async def test_async_get_device_detail_success(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test getting device detail successfully."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    mock_detail = {
        "deviceId": "device-1",
        "properties": [
            {"identifier": "temperature", "value": 25.0},
        ],
    }

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client._async_get_device_detail = AsyncMock(return_value=mock_detail)

        detail = await client.async_get_device_detail("device-1")

        assert detail == mock_detail


async def test_token_refresh_on_expired_token(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test token refresh when token expires."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_user_info = AsyncMock(
            side_effect=[
                HeimanAuthError("Token expired"),
                MagicMock(user_id="test-user"),
            ]
        )

        # First call should trigger auth error
        with pytest.raises(ConfigEntryAuthFailed):
            await client.async_get_user_info()

        # Token should have been refreshed
        mock_oauth_session.async_ensure_token_valid.assert_called()


async def test_api_client_with_token_data_only(hass: HomeAssistant) -> None:
    """Test API client using token data instead of session."""
    token_data = {
        "access_token": "direct-token",
        "refresh_token": "refresh-token",
        "expires_in": 3600,
    }

    client = HeimanApiClient(hass, token_data=token_data)

    assert client._get_access_token() == "direct-token"


async def test_api_client_connection_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test API client handles connection errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_user_info = AsyncMock(
            side_effect=HeimanConnectionError("Network error")
        )

        with pytest.raises(UpdateFailed):
            await client.async_get_user_info()


async def test_api_client_not_initialized(hass: HomeAssistant) -> None:
    """Test API client methods when not properly initialized."""
    client = HeimanApiClient(hass)  # No token provided

    with pytest.raises(HeimanConnectionError, match="Client not initialized"):
        await client.async_get_user_info()


async def test_token_refresh_transient_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test handling of OAuth2TokenRequestTransientError during token refresh."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    # Simulate transient error during token refresh
    mock_oauth_session.async_ensure_token_valid.side_effect = (
        OAuth2TokenRequestTransientError(
            request_info=MagicMock(),
            history=(),
            status=503,
            headers=None,
            domain="test",
        )
    )

    with pytest.raises(UpdateFailed, match="Temporary token refresh error"):
        await client.async_get_user_info()


async def test_token_refresh_unexpected_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test handling of unexpected errors during token refresh."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    # Simulate unexpected error during token refresh
    mock_oauth_session.async_ensure_token_valid.side_effect = RuntimeError(
        "Unexpected error"
    )

    with pytest.raises(UpdateFailed, match="Token refresh failed"):
        await client.async_get_user_info()


async def test_api_client_auth_reauth_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test handling of OAuth2TokenRequestReauthError during token refresh."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    # Simulate re-auth error during token refresh
    mock_oauth_session.async_ensure_token_valid.side_effect = (
        OAuth2TokenRequestReauthError(
            request_info=MagicMock(),
            history=(),
            status=401,
            headers=None,
            domain="test",
        )
    )

    with pytest.raises(ConfigEntryAuthFailed, match="Token expired"):
        await client.async_get_user_info()


async def test_async_get_homes_unexpected_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_homes handles unexpected errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_homes.side_effect = RuntimeError("Unexpected")

        with pytest.raises(HeimanConnectionError, match="Failed to get homes"):
            await client.async_get_homes()


async def test_async_get_devices_unexpected_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_devices handles unexpected errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_devices.side_effect = RuntimeError("Unexpected")

        with pytest.raises(HeimanConnectionError, match="Failed to get devices"):
            await client.async_get_devices(home_id="home-1")


async def test_async_control_device_success(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_control_device succeeds."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_control_device = AsyncMock(return_value=True)

        result = await client.async_control_device("device-1", "power", True)

        assert result is True


async def test_async_control_device_unexpected_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_control_device handles unexpected errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_control_device.side_effect = RuntimeError("Unexpected")

        with pytest.raises(HeimanConnectionError, match="Failed to control device"):
            await client.async_control_device("device-1", "power", True)


async def test_async_control_device_auth_failed(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_control_device handles authentication failure."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_control_device.side_effect = HeimanAuthError(
            "Auth failed"
        )

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await client.async_control_device("device-1", "power", True)


async def test_async_control_device_connection_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_control_device handles connection errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_control_device.side_effect = HeimanConnectionError(
            "Network error"
        )

        with pytest.raises(UpdateFailed, match="Connection error controlling device"):
            await client.async_control_device("device-1", "power", True)


async def test_async_get_device_detail_failure(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_device_detail handles failures gracefully."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client._async_get_device_detail = AsyncMock(
            side_effect=Exception("Error")
        )

        # Should return None on error, not raise
        result = await client.async_get_device_detail("device-1")
        assert result is None


async def test_async_get_device_detail_not_initialized(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_device_detail when cloud client is not initialized."""
    client = HeimanApiClient(hass)  # No session/token

    # Should return None when not initialized
    result = await client.async_get_device_detail("device-1")
    assert result is None


async def test_token_update_refreshes_client(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test that token update refreshes the HTTP client."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    # Store original HTTP client reference
    original_http_client = client._http_client
    assert original_http_client is not None

    # Update token
    new_token = "new-access-token"
    mock_oauth_session.token = {"access_token": new_token}

    # Call async_ensure_token_valid which should trigger client update
    with (
        patch.object(
            original_http_client, "update_access_token"
        ) as mock_update_access_token,
        patch.object(client, "_cloud_client") as mock_cloud_client,
    ):
        mock_cloud_client.async_get_user_info = AsyncMock(return_value=MagicMock())

        await client.async_get_user_info()

        # Verify token was updated in the HTTP client
        mock_update_access_token.assert_called_once_with(new_token)


async def test_api_client_close(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test API client close method."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_http_client") as mock_http_client:
        mock_http_client.close = AsyncMock()

        await client.close()

        mock_http_client.close.assert_called_once()


async def test_api_client_close_no_client(hass: HomeAssistant) -> None:
    """Test API client close when HTTP client is not initialized."""
    client = HeimanApiClient(hass)  # No token, so no HTTP client

    # Should not raise
    await client.close()


async def test_async_get_user_info_unexpected_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_user_info handles unexpected errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_user_info.side_effect = RuntimeError("Unexpected")

        with pytest.raises(Exception, match="Failed to get user info"):
            await client.async_get_user_info()


async def test_async_get_device_properties_auth_failed(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_device_properties handles authentication failure."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_device_properties.side_effect = HeimanAuthError(
            "Auth failed"
        )

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await client.async_get_device_properties("device-1")


async def test_async_get_device_properties_connection_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_device_properties handles connection errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_device_properties.side_effect = (
            HeimanConnectionError("Network error")
        )

        with pytest.raises(
            UpdateFailed, match="Connection error getting device properties"
        ):
            await client.async_get_device_properties("device-1")


async def test_async_get_device_properties_unexpected_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_device_properties handles unexpected errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_device_properties.side_effect = RuntimeError(
            "Unexpected"
        )

        with pytest.raises(Exception, match="Failed to get device properties"):
            await client.async_get_device_properties("device-1")


async def test_async_get_devices_auth_failed(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_devices handles authentication failure."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_devices.side_effect = HeimanAuthError("Auth failed")

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await client.async_get_devices(home_id="home-1")


async def test_async_get_devices_connection_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_devices handles connection errors."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_devices.side_effect = HeimanConnectionError(
            "Network error"
        )

        with pytest.raises(UpdateFailed, match="Connection error getting devices"):
            await client.async_get_devices(home_id="home-1")


async def test_async_get_homes_without_cloud_client(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_homes when cloud_client is not initialized."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with (
        patch.object(client, "_cloud_client", None),
        pytest.raises(HeimanConnectionError, match="Client not initialized"),
    ):
        await client.async_get_homes()


async def test_async_get_homes_auth_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_homes handles HeimanAuthError."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_homes.side_effect = HeimanAuthError("Auth failed")

        with pytest.raises(ConfigEntryAuthFailed, match="Authentication failed"):
            await client.async_get_homes()


async def test_async_get_homes_connection_error(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_homes handles HeimanConnectionError."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with patch.object(client, "_cloud_client") as mock_cloud_client:
        mock_cloud_client.async_get_homes.side_effect = HeimanConnectionError(
            "Network error"
        )

        with pytest.raises(UpdateFailed, match="Connection error getting homes"):
            await client.async_get_homes()


async def test_async_get_devices_without_cloud_client(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_devices when cloud_client is not initialized."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with (
        patch.object(client, "_cloud_client", None),
        pytest.raises(HeimanConnectionError, match="Client not initialized"),
    ):
        await client.async_get_devices(home_id="home-1")


async def test_async_get_device_properties_without_cloud_client(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_get_device_properties when cloud_client is not initialized."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with (
        patch.object(client, "_cloud_client", None),
        pytest.raises(HeimanConnectionError, match="Client not initialized"),
    ):
        await client.async_get_device_properties("device-1")


async def test_async_control_device_without_cloud_client(
    hass: HomeAssistant, mock_oauth_session: MagicMock
) -> None:
    """Test async_control_device when cloud_client is not initialized."""
    client = HeimanApiClient(hass, session=mock_oauth_session)

    with (
        patch.object(client, "_cloud_client", None),
        pytest.raises(HeimanConnectionError, match="Client not initialized"),
    ):
        await client.async_control_device("device-1", "property-id", "value")
