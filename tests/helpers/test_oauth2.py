"""Tests for the OAuth 2.0 helpers."""

from unittest.mock import AsyncMock, Mock, patch

from multidict import CIMultiDict
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import oauth2

from tests.test_util.aiohttp import AiohttpClientMocker

ACCESS_TOKEN = "mock-access-token"
TOKEN_URL = "https://example.com/token"


@pytest.mark.parametrize("code_verifier_length", [40, 129])
def test_generate_code_verifier_invalid_length(code_verifier_length: int) -> None:
    """Test generate_code_verifier with an invalid length."""
    with pytest.raises(ValueError):
        oauth2.generate_code_verifier(code_verifier_length)


@pytest.mark.parametrize("code_verifier", ["", "yyy", "a" * 129])
def test_compute_code_challenge_invalid_code_verifier(code_verifier: str) -> None:
    """Test compute_code_challenge with an invalid code_verifier."""
    with pytest.raises(ValueError):
        oauth2.compute_code_challenge(code_verifier)


@pytest.mark.parametrize(
    "header_name",
    [
        pytest.param("Authorization", id="canonical_casing"),
        pytest.param("authorization", id="lowercase"),
    ],
)
async def test_oauth2_request_replaces_caller_authorization_header(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    header_name: str,
) -> None:
    """Test the token replaces a caller supplied Authorization header."""
    aioclient_mock.post("https://example.com", status=201)

    await oauth2.async_oauth2_request(
        hass,
        {"access_token": ACCESS_TOKEN},
        "post",
        "https://example.com",
        headers={header_name: "Bearer caller supplied"},
    )

    assert len(aioclient_mock.mock_calls) == 1
    headers = CIMultiDict(aioclient_mock.mock_calls[0][3])

    # The token must not be sent as a second Authorization header
    assert headers.getall("Authorization") == [f"Bearer {ACCESS_TOKEN}"]


def test_build_authorize_url_keeps_endpoint_query() -> None:
    """Test the endpoint query survives and extra parameters come last."""
    url = oauth2.build_authorize_url(
        "https://example.com/authorize?p=signin",
        client_id="client",
        redirect_uri="https://ha.example.com/cb",
        state="state",
        extra={"scope": "openid"},
    )

    assert url == (
        "https://example.com/authorize?p=signin&response_type=code"
        "&client_id=client&redirect_uri=https://ha.example.com/cb"
        "&state=state&scope=openid"
    )


async def test_token_request_passes_headers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test extra headers reach the token endpoint."""
    aioclient_mock.post(TOKEN_URL, json={"access_token": "at"})

    result = await oauth2.async_token_request(
        hass,
        TOKEN_URL,
        {"grant_type": "refresh_token"},
        domain="test",
        headers={"Authorization": "Basic Y2xpZW50OnNlY3JldA=="},
    )

    assert result == {"access_token": "at"}
    assert aioclient_mock.mock_calls[0][3] == {
        "Authorization": "Basic Y2xpZW50OnNlY3JldA=="
    }


async def test_token_request_refuses_redirect(hass: HomeAssistant) -> None:
    """Test a redirect is an error when redirects are not followed."""
    # The aiohttp mock ignores allow_redirects, so the session is patched to see it.
    response = Mock(status=307, request_info=Mock(), history=(), headers={})
    session = Mock(post=AsyncMock(return_value=response))

    with (
        patch(
            "homeassistant.helpers.oauth2.async_get_clientsession",
            return_value=session,
        ),
        pytest.raises(OAuth2TokenRequestError) as exc_info,
    ):
        await oauth2.async_token_request(
            hass, TOKEN_URL, {}, domain="test", allow_redirects=False
        )

    session.post.assert_awaited_once_with(
        TOKEN_URL, data={}, headers=None, allow_redirects=False
    )
    response.release.assert_called_once()
    assert exc_info.value.status == 307
    assert not isinstance(exc_info.value, OAuth2TokenRequestReauthError)


@pytest.mark.parametrize(
    ("client_secret", "method", "expected_body", "expected_headers"),
    [
        pytest.param(
            "s:cr&t",
            "client_secret_basic",
            {"grant_type": "refresh_token"},
            # base64 of "my+client:s%3Acr%26t"
            {"Authorization": "Basic bXkrY2xpZW50OnMlM0FjciUyNnQ="},
            id="basic",
        ),
        pytest.param(
            "secret",
            "client_secret_post",
            {
                "grant_type": "refresh_token",
                "client_id": "my client",
                "client_secret": "secret",
            },
            {},
            id="post",
        ),
        pytest.param(
            None,
            "client_secret_basic",
            {"grant_type": "refresh_token", "client_id": "my client"},
            {},
            id="public-client",
        ),
    ],
)
def test_client_auth(
    client_secret: str | None,
    method: oauth2.ClientAuthMethod,
    expected_body: dict[str, str],
    expected_headers: dict[str, str],
) -> None:
    """Test the client authenticates with exactly one method."""
    assert oauth2.client_auth(
        {"grant_type": "refresh_token"}, "my client", client_secret, method
    ) == (expected_body, expected_headers)
