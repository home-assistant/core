"""Tests for the HA-side OAuth2Session-backed AbstractAuth."""

from http import HTTPStatus
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


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(HTTPStatus.BAD_REQUEST, id="400_invalid_grant"),
        pytest.param(HTTPStatus.UNAUTHORIZED, id="401_unauthorized"),
        pytest.param(HTTPStatus.FORBIDDEN, id="403_forbidden"),
    ],
)
async def test_credential_refresh_failure_raises_abrp_auth_error(
    status: HTTPStatus,
) -> None:
    """A credential-related refusal maps to the terminal AbrpAuthError."""
    session = _mock_session()
    err = _response_error(status)
    session.async_ensure_token_valid.side_effect = err
    auth = AbetterrouteplannerAuth(session)

    with pytest.raises(AbrpAuthError) as exc_info:
        await auth.async_get_access_token()

    assert exc_info.value.__cause__ is err


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(HTTPStatus.REQUEST_TIMEOUT, id="408_timeout"),
        pytest.param(HTTPStatus.TOO_MANY_REQUESTS, id="429_rate_limited"),
        pytest.param(HTTPStatus.SERVICE_UNAVAILABLE, id="503_unavailable"),
    ],
)
async def test_transient_refresh_failure_propagates_unchanged(
    status: HTTPStatus,
) -> None:
    """A transient refusal propagates so the library's backoff can recover."""
    session = _mock_session()
    err = _response_error(status)
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
