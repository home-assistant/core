"""Tests for the HA-side OAuth2Session-backed AbstractAuth.

:class:`AbetterrouteplannerAuth` adapts HA's ``OAuth2Session`` to the
library's :class:`aioabrp.AbstractAuth` contract. The library treats an
:class:`aioabrp.AbrpAuthError` as a terminal auth failure (stop the stream +
fire ``AUTH_FAILED``) and any other exception as transient (back off + retry),
so the mapping here must turn a refresh 4xx (revoked/rotated refresh token)
into ``AbrpAuthError`` while letting everything else propagate unchanged.
"""

from unittest.mock import AsyncMock, MagicMock

from aioabrp import AbrpAuthError
from aiohttp import ClientError, ClientResponseError
import pytest

from homeassistant.components.abetterrouteplanner.auth import AbetterrouteplannerAuth
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


def _mock_session(token: dict | None = None) -> MagicMock:
    """Build a spec'd OAuth2Session with an awaitable ensure-valid."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = token if token is not None else {"access_token": "valid-token"}
    return session


def _response_error(status: int) -> ClientResponseError:
    """Build a ClientResponseError with the given HTTP status."""
    return ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=status,
    )


async def test_async_get_access_token_returns_token() -> None:
    """A valid refresh returns the session's access token."""
    session = _mock_session({"access_token": "fresh-token"})
    auth = AbetterrouteplannerAuth(session)

    token = await auth.async_get_access_token()

    assert token == "fresh-token"
    session.async_ensure_token_valid.assert_awaited_once_with()


async def test_4xx_refresh_raises_abrp_auth_error() -> None:
    """A 400 refresh (revoked/rotated token) maps to a terminal AbrpAuthError."""
    session = _mock_session()
    err = _response_error(400)
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(AbrpAuthError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value.__cause__ is err


@pytest.mark.parametrize("status", [401, 403, 499])
async def test_other_4xx_refresh_raises_abrp_auth_error(status: int) -> None:
    """401/403 (and the rest of the 4xx range) also map to AbrpAuthError."""
    session = _mock_session()
    err = _response_error(status)
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(AbrpAuthError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value.__cause__ is err


async def test_5xx_refresh_propagates_as_client_response_error() -> None:
    """A 5xx refresh is transient — it propagates unchanged, not AbrpAuthError."""
    session = _mock_session()
    err = _response_error(503)
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(ClientResponseError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value is err


async def test_client_error_propagates_unchanged() -> None:
    """A generic ClientError is transient and propagates unchanged."""
    session = _mock_session()
    err = ClientError("boom")
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(ClientError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value is err


async def test_timeout_error_propagates_unchanged() -> None:
    """A timeout is transient and propagates unchanged."""
    session = _mock_session()
    err = TimeoutError()
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(TimeoutError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value is err
