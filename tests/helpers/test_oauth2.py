"""Tests for the OAuth 2.0 helpers."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import oauth2

from tests.test_util.aiohttp import AiohttpClientMocker

TOKEN_URL = "https://example.com/token"


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


async def test_token_request_refuses_redirect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test a redirect is an error when redirects are not followed."""
    aioclient_mock.post(TOKEN_URL, status=307, headers={"Location": "https://evil"})

    with pytest.raises(OAuth2TokenRequestError) as exc_info:
        await oauth2.async_token_request(
            hass, TOKEN_URL, {}, domain="test", allow_redirects=False
        )

    assert exc_info.value.status == 307
    assert not isinstance(exc_info.value, OAuth2TokenRequestReauthError)
