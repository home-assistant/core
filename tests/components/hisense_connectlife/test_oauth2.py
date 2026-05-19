"""Test Hisense OAuth2 implementation."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from connectlife_cloud import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
import pytest

from homeassistant.components.hisense_connectlife.const import DOMAIN
from homeassistant.components.hisense_connectlife.oauth2 import (
    HisenseOAuth2Implementation,
)
from homeassistant.core import HomeAssistant


async def test_implementation_initialization(hass: HomeAssistant) -> None:
    """Test OAuth2 implementation initialization."""
    impl = HisenseOAuth2Implementation(hass)
    assert impl.name == "Hisense AC"
    assert impl.domain == DOMAIN
    assert impl.authorize_url == OAUTH2_AUTHORIZE
    assert impl.token_url == OAUTH2_TOKEN


async def test_async_resolve_external_data(hass: HomeAssistant) -> None:
    """Test resolving external auth data."""
    external_data = {
        "code": "test_code",
        "state": {"redirect_uri": "https://example.com/callback"},
    }
    token_response = {
        "access_token": "at",
        "refresh_token": "rt",
        "expires_in": 3600,
    }

    impl = HisenseOAuth2Implementation(hass)

    with patch.object(impl, "_token_request", return_value=token_response) as mock_req:
        result = await impl.async_resolve_external_data(external_data)

    assert result == token_response
    mock_req.assert_awaited_once()


async def test_async_refresh_token(hass: HomeAssistant) -> None:
    """Test token refresh flow."""
    old_token = {
        "access_token": "old_at",
        "refresh_token": "old_rt",
        "expires_at": 123456,
    }
    new_token = {
        "access_token": "new_at",
        "refresh_token": "new_rt",
        "expires_in": 3600,
    }

    impl = HisenseOAuth2Implementation(hass)

    with patch.object(impl, "_token_request", return_value=new_token) as mock_req:
        result = await impl.async_refresh_token(old_token)

    assert result["access_token"] == "new_at"
    assert result["refresh_token"] == "new_rt"
    mock_req.assert_awaited_once()


@pytest.fixture
def oauth_impl(hass: HomeAssistant):
    """Create OAuth2 implementation fixture."""
    return HisenseOAuth2Implementation(hass)


async def test_token_request_with_expires(oauth_impl) -> None:
    """Test token request with expires_in → auto add expires_at."""
    test_data = {"grant_type": "authorization_code", "code": "test_code"}

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(
        return_value={"access_token": "a", "refresh_token": "r", "expires_in": 3600}
    )

    with (
        patch(
            "homeassistant.components.hisense_connectlife.oauth2.async_get_clientsession"
        ) as mock_acs,
        patch(
            "homeassistant.components.hisense_connectlife.oauth2.time.time",
            return_value=1000.0,
        ),
        patch.object(
            type(oauth_impl),
            "redirect_uri",
            new_callable=PropertyMock,
            return_value="https://example.com/callback",
        ),
    ):
        mock_session = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_resp)
        mock_acs.return_value = mock_session

        result = await oauth_impl._token_request(test_data)

    assert result["expires_at"] == 4600.0
    mock_session.post.assert_awaited_once()
    _, kwargs = mock_session.post.call_args
    assert kwargs["data"]["grant_type"] == "authorization_code"
    assert kwargs["data"]["code"] == "test_code"
    assert "client_id" in kwargs["data"]
    assert "client_secret" in kwargs["data"]
    assert "redirect_uri" in kwargs["data"]


async def test_token_request_no_expires(oauth_impl) -> None:
    """Test token request without expires_in."""
    test_data = {"grant_type": "refresh_token", "refresh_token": "test"}

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = AsyncMock(return_value={"access_token": "a", "refresh_token": "r"})

    with (
        patch(
            "homeassistant.components.hisense_connectlife.oauth2.async_get_clientsession"
        ) as mock_acs,
        patch.object(
            type(oauth_impl),
            "redirect_uri",
            new_callable=PropertyMock,
            return_value="https://example.com/callback",
        ),
    ):
        mock_session = MagicMock()
        mock_session.post = AsyncMock(return_value=mock_resp)
        mock_acs.return_value = mock_session

        result = await oauth_impl._token_request(test_data)

    assert "expires_at" not in result
    mock_session.post.assert_awaited_once()
    _, kwargs = mock_session.post.call_args
    assert kwargs["data"]["grant_type"] == "refresh_token"
    assert kwargs["data"]["refresh_token"] == "test"
    assert "client_id" in kwargs["data"]
    assert "client_secret" in kwargs["data"]
    assert "redirect_uri" in kwargs["data"]
