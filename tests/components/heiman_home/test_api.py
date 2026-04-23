"""Tests for Heiman Home API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from heimanconnect import HeimanAuthError, HeimanConnectionError

from homeassistant.components.heiman_home.api import HeimanApiClient
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_api_client_get_access_token_from_session(hass: HomeAssistant) -> None:
    """Test getting access token from OAuth2 session."""
    mock_session = MagicMock()
    mock_session.token = {"access_token": "test-token-123"}

    client = HeimanApiClient(hass, session=mock_session)

    token = await client._get_access_token()
    assert token == "test-token-123"


async def test_api_client_get_access_token_from_token_data(hass: HomeAssistant) -> None:
    """Test getting access token from token data."""
    token_data = {"access_token": "test-token-456"}

    client = HeimanApiClient(hass, token_data=token_data)

    token = await client._get_access_token()
    assert token == "test-token-456"


async def test_api_client_get_access_token_none(hass: HomeAssistant) -> None:
    """Test getting access token when none available."""
    client = HeimanApiClient(hass)

    token = await client._get_access_token()
    assert token is None


async def test_api_client_ensure_initialized_success(hass: HomeAssistant) -> None:
    """Test successful client initialization."""
    token_data = {"access_token": "test-token"}
    client = HeimanApiClient(hass, token_data=token_data)

    with patch(
        "homeassistant.components.heiman_home.api.HeimanCloudClientWrapper"
    ) as mock_wrapper_class:
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper

        await client._ensure_initialized()

        assert client._wrapper is not None
        mock_wrapper_class.assert_called_once()


async def test_api_client_ensure_initialized_no_token(hass: HomeAssistant) -> None:
    """Test initialization fails when no token available."""
    client = HeimanApiClient(hass)

    with pytest.raises(HeimanConnectionError, match="No access token available"):
        await client._ensure_initialized()


async def test_api_client_ensure_initialized_already_initialized(hass: HomeAssistant) -> None:
    """Test that already initialized client is not re-initialized."""
    token_data = {"access_token": "test-token"}
    client = HeimanApiClient(hass, token_data=token_data)

    with patch(
        "homeassistant.components.heiman_home.api.HeimanCloudClientWrapper"
    ) as mock_wrapper_class:
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper

        # First initialization
        await client._ensure_initialized()
        first_call_count = mock_wrapper_class.call_count

        # Second call should not create new wrapper
        await client._ensure_initialized()

        assert mock_wrapper_class.call_count == first_call_count


async def test_api_client_refresh_token_callback_success(hass: HomeAssistant) -> None:
    """Test successful token refresh."""
    mock_session = MagicMock()
    mock_session.token = {"access_token": "new-token"}
    mock_session.async_ensure_token_valid = AsyncMock()

    client = HeimanApiClient(hass, session=mock_session)

    new_token = await client._refresh_token_callback()
    assert new_token == "new-token"
    mock_session.async_ensure_token_valid.assert_called_once()


async def test_api_client_refresh_token_transient_error(hass: HomeAssistant) -> None:
    """Test token refresh with transient error."""
    # This test covers line 94-95 in api.py
    from aiohttp import RequestInfo
    from homeassistant.exceptions import OAuth2TokenRequestTransientError
    from yarl import URL

    mock_session = MagicMock()
    # Create the specific OAuth2 exception that HA framework raises
    request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_session.async_ensure_token_valid = AsyncMock(
        side_effect=OAuth2TokenRequestTransientError(
            domain="heiman_home",
            request_info=request_info,
        )
    )

    client = HeimanApiClient(hass, session=mock_session)

    # Should raise UpdateFailed wrapping the transient error
    with pytest.raises(UpdateFailed):
        await client._refresh_token_callback()


async def test_api_client_refresh_token_reauth_error(hass: HomeAssistant) -> None:
    """Test token refresh with reauth error."""
    # This test covers line 96-97 in api.py
    from aiohttp import RequestInfo
    from homeassistant.exceptions import OAuth2TokenRequestReauthError
    from yarl import URL

    mock_session = MagicMock()
    # Create the specific OAuth2 exception that HA framework raises
    request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_session.async_ensure_token_valid = AsyncMock(
        side_effect=OAuth2TokenRequestReauthError(
            domain="heiman_home",
            request_info=request_info,
        )
    )

    client = HeimanApiClient(hass, session=mock_session)

    # Should raise ConfigEntryAuthFailed for reauth errors
    with pytest.raises(ConfigEntryAuthFailed):
        await client._refresh_token_callback()


async def test_api_client_refresh_token_generic_exception(hass: HomeAssistant) -> None:
    """Test token refresh with generic exception."""
    mock_session = MagicMock()
    mock_session.async_ensure_token_valid = AsyncMock(
        side_effect=Exception("Unknown error")
    )

    client = HeimanApiClient(hass, session=mock_session)

    with pytest.raises(UpdateFailed, match="Token refresh failed"):
        await client._refresh_token_callback()


async def test_api_client_refresh_token_no_new_token(hass: HomeAssistant) -> None:
    """Test token refresh when no new token is returned."""
    mock_session = MagicMock()
    mock_session.token = {}  # Empty token after refresh
    mock_session.async_ensure_token_valid = AsyncMock()

    client = HeimanApiClient(hass, session=mock_session)

    with pytest.raises(HeimanAuthError, match="No token available for refresh"):
        await client._refresh_token_callback()


async def test_api_client_refresh_token_fallback_to_token_data(hass: HomeAssistant) -> None:
    """Test token refresh falls back to token_data."""
    mock_session = MagicMock()
    mock_session.token = {}  # No token in session
    mock_session.async_ensure_token_valid = AsyncMock()

    token_data = {"access_token": "fallback-token"}
    client = HeimanApiClient(hass, session=mock_session, token_data=token_data)

    new_token = await client._refresh_token_callback()
    assert new_token == "fallback-token"


async def test_api_client_cloud_client_property(hass: HomeAssistant) -> None:
    """Test cloud_client property returns wrapper."""
    token_data = {"access_token": "test-token"}
    client = HeimanApiClient(hass, token_data=token_data)

    with patch(
        "homeassistant.components.heiman_home.api.HeimanCloudClientWrapper"
    ) as mock_wrapper_class:
        mock_wrapper = MagicMock()
        mock_wrapper_class.return_value = mock_wrapper

        await client._ensure_initialized()

        assert client.cloud_client is mock_wrapper


async def test_api_client_cloud_client_not_initialized(hass: HomeAssistant) -> None:
    """Test cloud_client property raises error when not initialized."""
    client = HeimanApiClient(hass)

    with pytest.raises(RuntimeError, match="Client not initialized"):
        _ = client.cloud_client


async def test_api_client_close(hass: HomeAssistant) -> None:
    """Test closing the API client."""
    token_data = {"access_token": "test-token"}
    client = HeimanApiClient(hass, token_data=token_data)

    with patch(
        "homeassistant.components.heiman_home.api.HeimanCloudClientWrapper"
    ) as mock_wrapper_class:
        mock_wrapper = MagicMock()
        mock_wrapper.close = AsyncMock()
        mock_wrapper_class.return_value = mock_wrapper

        await client._ensure_initialized()
        await client.close()

        mock_wrapper.close.assert_called_once()
        assert client._wrapper is None


async def test_api_client_close_not_initialized(hass: HomeAssistant) -> None:
    """Test closing client that was never initialized."""
    client = HeimanApiClient(hass)

    # Should not raise any error
    await client.close()
    assert client._wrapper is None
