"""Tests for the HA-side OAuth2Session-backed AbstractAuth."""

from unittest.mock import AsyncMock, MagicMock

from aioabrp import AbrpAuthError
from aiohttp import ClientError
import pytest

from homeassistant.components.abetterrouteplanner.auth import AbetterrouteplannerAuth
from homeassistant.components.abetterrouteplanner.const import DOMAIN
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session


def _mock_session(token: dict | None = None) -> MagicMock:
    """Build a spec'd OAuth2Session with an awaitable ensure-valid."""
    session = MagicMock(spec=OAuth2Session)
    session.async_ensure_token_valid = AsyncMock()
    session.token = token if token is not None else {"access_token": "valid-token"}
    return session


def _token_error(
    error_type: type[OAuth2TokenRequestError],
) -> OAuth2TokenRequestError:
    """Build one of the helper's token-refresh errors.

    The adapter dispatches on the error's type, so the HTTP status the helper
    classified it from carries no meaning here.
    """
    return error_type(request_info=MagicMock(), history=(), domain=DOMAIN)


async def test_async_get_access_token_returns_token() -> None:
    """A valid refresh returns the session's access token."""
    session = _mock_session({"access_token": "fresh-token"})
    auth = AbetterrouteplannerAuth(session)

    token = await auth.async_get_access_token()

    assert token == "fresh-token"
    session.async_ensure_token_valid.assert_awaited_once_with()


async def test_reauth_refresh_failure_raises_abrp_auth_error() -> None:
    """The helper's terminal verdict maps to the terminal AbrpAuthError."""
    session = _mock_session()
    err = _token_error(OAuth2TokenRequestReauthError)
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(AbrpAuthError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value.__cause__ is err


@pytest.mark.parametrize(
    "error_type",
    [
        pytest.param(OAuth2TokenRequestTransientError, id="transient"),
        pytest.param(OAuth2TokenRequestError, id="unclassified"),
    ],
)
async def test_non_terminal_refresh_failure_propagates_unchanged(
    error_type: type[OAuth2TokenRequestError],
) -> None:
    """A non-terminal refusal propagates so the library's backoff can recover."""
    session = _mock_session()
    err = _token_error(error_type)
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(OAuth2TokenRequestError) as exc_info:
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
