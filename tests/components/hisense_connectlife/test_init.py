"""Test the Hisense ConnectLife integration initialization."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.hisense_connectlife import (
    PLATFORMS,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)


@pytest.mark.asyncio
async def test_async_setup(hass: HomeAssistant) -> None:
    """Test async_setup registers OAuth2 implementation."""
    with (
        patch(
            "homeassistant.components.hisense_connectlife.HisenseOAuth2Implementation"
        ) as mock_impl,
        patch(
            "homeassistant.components.hisense_connectlife.OAuth2FlowHandler.async_register_implementation"
        ) as mock_register,
    ):
        mock_impl_instance = MagicMock()
        mock_impl.return_value = mock_impl_instance

        result = await async_setup(hass, {})

        assert result is True
        mock_impl.assert_called_once_with(hass)
        mock_register.assert_called_once_with(hass, mock_impl_instance)


@pytest.mark.asyncio
async def test_async_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry successfully sets up the integration."""
    mock_config_entry.data = {CONF_TOKEN: {CONF_ACCESS_TOKEN: "test_access_token"}}

    with (
        patch(
            "homeassistant.components.hisense_connectlife.async_get_config_entry_implementation"
        ) as mock_get_impl,
        patch(
            "homeassistant.components.hisense_connectlife.OAuth2Session"
        ) as mock_oauth_session_cls,
        patch(
            "homeassistant.components.hisense_connectlife.HisenseApiClient"
        ) as mock_api_client_cls,
        patch(
            "homeassistant.components.hisense_connectlife.HisenseACPluginDataUpdateCoordinator"
        ) as mock_coordinator_cls,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
        ) as mock_forward,
    ):
        # Mock implementation
        mock_implementation = MagicMock()
        mock_get_impl.return_value = mock_implementation

        # Mock OAuth2Session
        mock_oauth_session = AsyncMock()
        mock_oauth_session.async_ensure_token_valid = AsyncMock()
        mock_oauth_session_cls.return_value = mock_oauth_session

        # Mock API client
        mock_api_client = MagicMock()
        mock_api_client_cls.return_value = mock_api_client

        # Mock coordinator
        mock_coordinator = AsyncMock()
        mock_coordinator.async_setup = AsyncMock()
        mock_coordinator_cls.return_value = mock_coordinator

        result = await async_setup_entry(hass, mock_config_entry)

        assert result is True
        mock_get_impl.assert_called_once_with(hass, mock_config_entry)
        mock_coordinator_cls.assert_called_once_with(
            hass, mock_api_client, mock_config_entry
        )
        mock_coordinator.async_setup.assert_called_once()
        mock_forward.assert_called_once_with(mock_config_entry, PLATFORMS)
        assert mock_config_entry.runtime_data == mock_coordinator


@pytest.mark.asyncio
async def test_async_setup_entry_implementation_unavailable(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady when implementation unavailable."""
    with patch(
        "homeassistant.components.hisense_connectlife.async_get_config_entry_implementation"
    ) as mock_get_impl:
        mock_get_impl.side_effect = ImplementationUnavailableError("Unavailable")

        with pytest.raises(
            ConfigEntryNotReady, match="OAuth2 implementation temporarily unavailable"
        ):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_auth_failure(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry raises ConfigEntryAuthFailed on 4xx errors."""
    mock_config_entry.data = {CONF_TOKEN: {CONF_ACCESS_TOKEN: "test_access_token"}}

    with (
        patch(
            "homeassistant.components.hisense_connectlife.async_get_config_entry_implementation"
        ) as mock_get_impl,
        patch(
            "homeassistant.components.hisense_connectlife.OAuth2Session"
        ) as mock_oauth_session_cls,
    ):
        mock_implementation = MagicMock()
        mock_get_impl.return_value = mock_implementation

        mock_oauth_session = AsyncMock()
        mock_oauth_session.async_ensure_token_valid = AsyncMock()
        mock_oauth_session_cls.return_value = mock_oauth_session

        # First call succeeds, second call raises 401
        mock_oauth_session.async_ensure_token_valid.side_effect = [
            None,
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=401,
                message="Unauthorized",
            ),
        ]

        with pytest.raises(
            ConfigEntryAuthFailed, match="OAuth session is not valid, reauth required"
        ):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_setup_entry_client_error(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_setup_entry raises ConfigEntryNotReady on client error."""
    mock_config_entry.data = {CONF_TOKEN: {CONF_ACCESS_TOKEN: "test_access_token"}}

    with (
        patch(
            "homeassistant.components.hisense_connectlife.async_get_config_entry_implementation"
        ) as mock_get_impl,
        patch(
            "homeassistant.components.hisense_connectlife.OAuth2Session"
        ) as mock_oauth_session_cls,
    ):
        mock_implementation = MagicMock()
        mock_get_impl.return_value = mock_implementation

        mock_oauth_session = AsyncMock()
        mock_oauth_session.async_ensure_token_valid = AsyncMock()
        mock_oauth_session_cls.return_value = mock_oauth_session

        # First call succeeds, second call raises ClientError
        mock_oauth_session.async_ensure_token_valid.side_effect = [
            None,
            ClientResponseError(
                request_info=MagicMock(),
                history=(),
                status=500,
                message="Server Error",
            ),
        ]

        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry)


@pytest.mark.asyncio
async def test_async_unload_entry_success(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_unload_entry successfully unloads the integration."""
    mock_coordinator = AsyncMock()
    mock_coordinator.api_client.oauth_session.close = AsyncMock()
    mock_config_entry.runtime_data = mock_coordinator

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is True
        mock_unload.assert_called_once_with(mock_config_entry, PLATFORMS)
        mock_coordinator.api_client.oauth_session.close.assert_called_once()
        assert mock_config_entry.runtime_data is None


@pytest.mark.asyncio
async def test_async_unload_entry_false(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """Test async_unload_entry returns False when unload fails."""
    mock_coordinator = AsyncMock()
    mock_config_entry.runtime_data = mock_coordinator

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=False,
    ):
        result = await async_unload_entry(hass, mock_config_entry)

        assert result is False
        # Should not close or clear runtime_data when unload fails
