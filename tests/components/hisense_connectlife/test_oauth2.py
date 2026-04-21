"""Test Hisense OAuth2 implementation."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from connectlife_cloud import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
import pytest

from homeassistant.components.hisense_connectlife.const import DOMAIN
from homeassistant.components.hisense_connectlife.oauth2 import (
    HisenseOAuth2Implementation,
    OAuth2Session,
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


async def test_oauth2_session_initialize(hass: HomeAssistant) -> None:
    """Test OAuth2Session initialization."""
    impl = HisenseOAuth2Implementation(hass)
    token = {"access_token": "at", "refresh_token": "rt"}

    session = OAuth2Session(hass, impl, token)

    assert session.token == token
    assert session.oauth2_implementation == impl
    assert session.hass == hass


async def test_is_token_expired(hass: HomeAssistant) -> None:
    """Test token expired logic."""
    impl = HisenseOAuth2Implementation(hass)

    # No expires_at or expires_in → expired
    session = OAuth2Session(hass, impl, {})
    assert session._is_token_expired() is True

    # Has expires_in → not expired
    session = OAuth2Session(hass, impl, {"expires_in": 3600})
    assert session._is_token_expired() is False
    assert "expires_at" in session.token

    # Expired (now >= expires_at - 300)
    session = OAuth2Session(hass, impl, {"expires_at": 1})
    assert session._is_token_expired() is True


async def test_async_ensure_token_valid_not_expired(hass: HomeAssistant) -> None:
    """Test ensure token valid when token is still valid."""
    impl = HisenseOAuth2Implementation(hass)
    token = {"access_token": "at", "expires_at": 9999999999}
    session = OAuth2Session(hass, impl, token)

    await session.async_ensure_token_valid()
    assert session.token["access_token"] == "at"


async def test_async_ensure_token_valid_refresh(hass: HomeAssistant) -> None:
    """Test ensure token valid triggers refresh."""
    impl = HisenseOAuth2Implementation(hass)
    old_token = {"access_token": "old", "refresh_token": "rt", "expires_at": 1}
    new_token = {"access_token": "new", "expires_in": 3600}

    session = OAuth2Session(hass, impl, old_token)

    with patch.object(
        impl, "async_refresh_token", return_value=new_token
    ) as mock_refresh:
        await session.async_ensure_token_valid()

    mock_refresh.assert_awaited_once_with(old_token)
    assert session.token["access_token"] == "new"


async def test_async_get_access_token(hass: HomeAssistant) -> None:
    """Test getting access token."""
    impl = HisenseOAuth2Implementation(hass)
    token = {"access_token": "valid_at", "expires_at": 9999999999}
    session = OAuth2Session(hass, impl, token)

    access_token = await session.async_get_access_token()
    assert access_token == "valid_at"


async def test_close(hass: HomeAssistant) -> None:
    """Test close does nothing."""
    impl = HisenseOAuth2Implementation(hass)
    session = OAuth2Session(hass, impl, {})
    await session.close()


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
