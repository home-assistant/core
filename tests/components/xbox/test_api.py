"""Tests for the xbox API authentication."""

from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.components.xbox.api import AsyncConfigEntryAuth

SETUP_TOKEN: dict[str, Any] = {
    "access_token": "token_at_setup",
    "expires_at": 1760697327.7298331,
    "expires_in": 3600,
    "refresh_token": "refresh_at_setup",
    "scope": "XboxLive.signin XboxLive.offline_access",
    "service": "xbox",
    "token_type": "bearer",
    "user_id": "AAAAAAAAAAAAAAAAAAAAA",
}

REPLACEMENT_TOKEN: dict[str, Any] = {
    **SETUP_TOKEN,
    "access_token": "token_after_replacement",
    "expires_at": 1760700927.7298331,
    "refresh_token": "refresh_after_replacement",
}


async def test_token_replaced_without_refresh_is_used() -> None:
    """Test a token replaced without a refresh is picked up.

    Reauth writes a new token to the config entry, but the entry is only
    reloaded when its subentries or auth implementation change. The
    replacement token has a future expiry, so `valid_token` is True and no
    refresh is triggered. It still has to be picked up, otherwise the dead
    token captured when this object was created keeps being used until it
    fails and triggers reauth again.
    """

    oauth_session = AsyncMock()
    oauth_session.token = SETUP_TOKEN

    auth = AsyncConfigEntryAuth(AsyncMock(), oauth_session)
    assert auth.oauth.access_token == "token_at_setup"

    # Reauth replaces the token in the config entry, without a reload.
    oauth_session.token = REPLACEMENT_TOKEN
    oauth_session.valid_token = True

    with patch(
        "homeassistant.components.xbox.api.AuthenticationManager.refresh_tokens"
    ):
        await auth.refresh_tokens()

    oauth_session.async_ensure_token_valid.assert_not_called()
    assert auth.oauth.access_token == "token_after_replacement"
    assert auth.oauth.refresh_token == "refresh_after_replacement"


async def test_expired_token_is_refreshed() -> None:
    """Test an expired token is refreshed and the refreshed token is used."""

    oauth_session = AsyncMock()
    oauth_session.token = SETUP_TOKEN
    oauth_session.valid_token = False

    auth = AsyncConfigEntryAuth(AsyncMock(), oauth_session)

    async def _replace_token() -> None:
        oauth_session.token = REPLACEMENT_TOKEN

    oauth_session.async_ensure_token_valid.side_effect = _replace_token

    with patch(
        "homeassistant.components.xbox.api.AuthenticationManager.refresh_tokens"
    ):
        await auth.refresh_tokens()

    oauth_session.async_ensure_token_valid.assert_awaited_once()
    assert auth.oauth.access_token == "token_after_replacement"
