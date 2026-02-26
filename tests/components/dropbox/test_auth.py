"""Test the Dropbox authentication."""

from __future__ import annotations

from unittest.mock import AsyncMock

from aiohttp import ClientSession

from homeassistant.components.dropbox.auth import (
    AsyncConfigEntryAuth,
    AsyncConfigFlowAuth,
)


async def test_config_entry_auth_get_access_token() -> None:
    """Test that config entry auth returns a valid access token."""
    oauth_session = AsyncMock()
    oauth_session.token = {"access_token": "test-access-token"}

    auth = AsyncConfigEntryAuth(AsyncMock(spec=ClientSession), oauth_session)
    token = await auth.async_get_access_token()

    assert token == "test-access-token"
    oauth_session.async_ensure_token_valid.assert_awaited_once()


async def test_config_flow_auth_get_access_token() -> None:
    """Test that config flow auth returns the fixed token."""
    auth = AsyncConfigFlowAuth(AsyncMock(spec=ClientSession), "fixed-token")
    token = await auth.async_get_access_token()

    assert token == "fixed-token"
