"""Tests for the Google Mail auth API."""

from unittest.mock import AsyncMock, Mock

from aiohttp.client_exceptions import ClientResponseError
from google.auth.exceptions import RefreshError
import pytest

from homeassistant.components.google_mail.api import AsyncConfigEntryAuth
from homeassistant.components.google_mail.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)


def _build_auth(
    state: ConfigEntryState,
) -> tuple[AsyncConfigEntryAuth, Mock, Mock]:
    """Create a Google Mail auth object with a mocked OAuth session."""
    config_entry = Mock()
    config_entry.state = state
    config_entry.async_start_reauth = Mock()

    oauth_session = Mock()
    oauth_session.config_entry = config_entry
    oauth_session.hass = Mock()
    oauth_session.token = {"access_token": "token"}
    oauth_session.async_ensure_token_valid = AsyncMock()

    auth = AsyncConfigEntryAuth(Mock(), oauth_session)
    return auth, oauth_session, config_entry


async def test_check_and_refresh_token_success() -> None:
    """Test successful token validation returns the access token."""
    auth, _, _ = _build_auth(ConfigEntryState.LOADED)

    token = await auth.check_and_refresh_token()

    assert token == "token"


async def test_check_and_refresh_token_setup_reauth_error() -> None:
    """Test reauth errors during setup map to ConfigEntryAuthFailed."""
    auth, oauth_session, config_entry = _build_auth(ConfigEntryState.SETUP_IN_PROGRESS)
    oauth_session.async_ensure_token_valid.side_effect = OAuth2TokenRequestReauthError(
        domain=DOMAIN, request_info=Mock()
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await auth.check_and_refresh_token()

    config_entry.async_start_reauth.assert_not_called()


async def test_check_and_refresh_token_setup_transient_error() -> None:
    """Test transient errors during setup map to ConfigEntryNotReady."""
    auth, oauth_session, config_entry = _build_auth(ConfigEntryState.SETUP_IN_PROGRESS)
    oauth_session.async_ensure_token_valid.side_effect = (
        OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=Mock())
    )

    with pytest.raises(ConfigEntryNotReady):
        await auth.check_and_refresh_token()

    config_entry.async_start_reauth.assert_not_called()


async def test_check_and_refresh_token_runtime_reauth_error() -> None:
    """Test runtime reauth errors trigger reauth and raise HomeAssistantError."""
    auth, oauth_session, config_entry = _build_auth(ConfigEntryState.LOADED)
    oauth_session.async_ensure_token_valid.side_effect = OAuth2TokenRequestReauthError(
        domain=DOMAIN, request_info=Mock()
    )

    with pytest.raises(HomeAssistantError):
        await auth.check_and_refresh_token()

    config_entry.async_start_reauth.assert_called_once_with(oauth_session.hass)


async def test_check_and_refresh_token_runtime_transient_error() -> None:
    """Test runtime transient errors raise HomeAssistantError without reauth."""
    auth, oauth_session, config_entry = _build_auth(ConfigEntryState.LOADED)
    oauth_session.async_ensure_token_valid.side_effect = (
        OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=Mock())
    )

    with pytest.raises(HomeAssistantError):
        await auth.check_and_refresh_token()

    config_entry.async_start_reauth.assert_not_called()


async def test_check_and_refresh_token_legacy_refresh_error() -> None:
    """Test legacy refresh errors still trigger reauth at runtime."""
    auth, _, config_entry = _build_auth(ConfigEntryState.LOADED)
    auth.oauth_session.async_ensure_token_valid.side_effect = RefreshError

    with pytest.raises(HomeAssistantError):
        await auth.check_and_refresh_token()

    config_entry.async_start_reauth.assert_called_once_with(auth.oauth_session.hass)


async def test_check_and_refresh_token_legacy_client_response_4xx() -> None:
    """Test legacy 4xx response errors still trigger reauth at runtime."""
    auth, _, config_entry = _build_auth(ConfigEntryState.LOADED)
    auth.oauth_session.async_ensure_token_valid.side_effect = ClientResponseError(
        request_info=Mock(), history=(), status=401
    )

    with pytest.raises(HomeAssistantError):
        await auth.check_and_refresh_token()

    config_entry.async_start_reauth.assert_called_once_with(auth.oauth_session.hass)
