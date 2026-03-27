"""Test the Eve Online API authentication helper."""

from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
import pytest

from homeassistant.components.eveonline.api import AsyncConfigEntryAuth
from homeassistant.components.eveonline.const import DOMAIN
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)


def _make_auth(
    token_valid_side_effect: Exception | None = None,
) -> AsyncConfigEntryAuth:
    """Create an AsyncConfigEntryAuth with a mocked OAuth2Session."""
    websession = MagicMock(spec=aiohttp.ClientSession)
    oauth_session = AsyncMock()
    oauth_session.async_ensure_token_valid = AsyncMock(
        side_effect=token_valid_side_effect
    )
    oauth_session.token = {"access_token": "mock-token"}
    return AsyncConfigEntryAuth(websession, oauth_session)


async def test_get_access_token_success() -> None:
    """Test that a valid access token is returned."""
    auth = _make_auth()
    token = await auth.async_get_access_token()
    assert token == "mock-token"


async def test_get_access_token_reauth_error() -> None:
    """Test that OAuth2TokenRequestReauthError raises ConfigEntryAuthFailed."""
    auth = _make_auth(OAuth2TokenRequestReauthError(domain=DOMAIN, request_info=Mock()))
    with pytest.raises(ConfigEntryAuthFailed):
        await auth.async_get_access_token()


async def test_get_access_token_transient_error() -> None:
    """Test that OAuth2TokenRequestTransientError raises ConfigEntryNotReady."""
    auth = _make_auth(
        OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=Mock())
    )
    with pytest.raises(ConfigEntryNotReady):
        await auth.async_get_access_token()


async def test_get_access_token_client_error() -> None:
    """Test that aiohttp.ClientError raises ConfigEntryNotReady."""
    auth = _make_auth(aiohttp.ClientError("network"))
    with pytest.raises(ConfigEntryNotReady):
        await auth.async_get_access_token()
