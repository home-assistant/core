"""Tests for Heiman Home application credentials."""

from json import JSONDecodeError
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientError, ClientResponse, RequestInfo
import pytest
from yarl import URL

from homeassistant.components.heiman_home.application_credentials import (
    HeimanOAuth2Implementation,
    async_get_auth_implementation,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)


async def test_async_get_auth_implementation(hass: HomeAssistant) -> None:
    """Test getting auth implementation."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = await async_get_auth_implementation(hass, "heiman_home", credential)

    assert isinstance(impl, HeimanOAuth2Implementation)
    assert impl.client_id == "test-client-id"
    assert impl.client_secret == "test-client-secret"


async def test_token_request_success(hass: HomeAssistant) -> None:
    """Test successful token request."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock the session and response
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"access_token": "test-token"})
    mock_response.text = AsyncMock(return_value='{"access_token": "test-token"}')
    mock_response.release = MagicMock()

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        result = await impl._token_request({"grant_type": "authorization_code"})

        assert result == {"access_token": "test-token"}
        mock_session.post.assert_called_once()


async def test_token_request_error_status(hass: HomeAssistant) -> None:
    """Test token request with error status."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock error response
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 400
    mock_response.json = AsyncMock(
        return_value={"error": "invalid_grant", "error_description": "Token expired"}
    )
    mock_response.text = AsyncMock(return_value='{"error": "invalid_grant"}')
    mock_response.release = MagicMock()
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.headers = {}

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestReauthError),
    ):
        await impl._token_request({"grant_type": "refresh_token"})


async def test_token_request_server_error(hass: HomeAssistant) -> None:
    """Test token request with server error (5xx)."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock server error response
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 500
    mock_response.json = AsyncMock(
        return_value={"error": "server_error", "error_description": "Internal error"}
    )
    mock_response.text = AsyncMock(return_value='{"error": "server_error"}')
    mock_response.release = MagicMock()
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.headers = {}

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestTransientError),
    ):
        await impl._token_request({"grant_type": "refresh_token"})


async def test_token_request_client_error(hass: HomeAssistant) -> None:
    """Test token request with client error."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    mock_session = MagicMock()
    mock_session.post = AsyncMock(side_effect=ClientError("Connection failed"))

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestTransientError),
    ):
        await impl._token_request({"grant_type": "refresh_token"})


async def test_token_request_timeout(hass: HomeAssistant) -> None:
    """Test token request with timeout."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    mock_session = MagicMock()
    mock_session.post = AsyncMock(side_effect=TimeoutError("Request timed out"))

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestTransientError),
    ):
        await impl._token_request({"grant_type": "refresh_token"})


async def test_parse_token_response_empty(hass: HomeAssistant) -> None:
    """Test parsing empty token response."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.text = AsyncMock(return_value="")
    mock_response.status = 200

    with pytest.raises(ValueError, match="Empty response"):
        await impl._parse_token_response(mock_response)


async def test_parse_token_response_invalid_json(hass: HomeAssistant) -> None:
    """Test parsing invalid JSON response."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.text = AsyncMock(return_value="not json")
    mock_response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
    mock_response.status = 200
    mock_response.content_type = "text/html"

    with pytest.raises(ValueError):
        await impl._parse_token_response(mock_response)


async def test_parse_token_response_valid(hass: HomeAssistant) -> None:
    """Test parsing valid token response."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.text = AsyncMock(return_value='{"access_token": "test"}')
    mock_response.json = AsyncMock(return_value={"access_token": "test"})
    mock_response.status = 200

    result = await impl._parse_token_response(mock_response)
    assert result == {"access_token": "test"}


async def test_raise_token_error_invalid_grant(hass: HomeAssistant) -> None:
    """Test raising token error for invalid_grant."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.status = 400
    mock_response.headers = {}

    with pytest.raises(OAuth2TokenRequestReauthError):
        impl._raise_token_error(mock_response, "invalid_grant")


async def test_raise_token_error_invalid_token(hass: HomeAssistant) -> None:
    """Test raising token error for invalid_token."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.status = 401
    mock_response.headers = {}

    with pytest.raises(OAuth2TokenRequestReauthError):
        impl._raise_token_error(mock_response, "invalid_token")


async def test_raise_token_error_server_error(hass: HomeAssistant) -> None:
    """Test raising token error for server error."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.status = 500
    mock_response.headers = {}

    with pytest.raises(OAuth2TokenRequestTransientError):
        impl._raise_token_error(mock_response, "server_error")


async def test_raise_token_error_other_error(hass: HomeAssistant) -> None:
    """Test raising token error for other errors."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.status = 400
    mock_response.headers = {}

    with pytest.raises(OAuth2TokenRequestError):
        impl._raise_token_error(mock_response, "unknown_error")


async def test_token_request_json_decode_error(hass: HomeAssistant) -> None:
    """Test token request when JSON decode fails on error response."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock error response that fails to parse as JSON
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 400
    mock_response.json = AsyncMock(
        side_effect=JSONDecodeError("Expecting value", "", 0)
    )
    mock_response.text = AsyncMock(return_value="Not valid JSON")
    mock_response.release = MagicMock()
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.headers = {}

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestError),
    ):
        # When JSON decode fails, error_code is "unknown" which raises OAuth2TokenRequestError
        await impl._token_request({"grant_type": "refresh_token"})


async def test_token_request_parse_response_error(hass: HomeAssistant) -> None:
    """Test token request when response parsing fails."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock response that succeeds but has invalid content
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value="Invalid response")
    mock_response.json = AsyncMock(side_effect=ValueError("Cannot parse"))
    mock_response.content_type = "text/html"
    mock_response.release = MagicMock()
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.headers = {}

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestError),
    ):
        await impl._token_request({"grant_type": "refresh_token"})


async def test_parse_token_response_non_json_with_logging(hass: HomeAssistant) -> None:
    """Test parsing non-JSON response triggers logging."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )

    mock_response = MagicMock(spec=ClientResponse)
    mock_response.text = AsyncMock(return_value="Not JSON at all")
    mock_response.json = AsyncMock(
        side_effect=JSONDecodeError("Expecting value", "", 0)
    )
    mock_response.status = 200
    mock_response.content_type = "text/plain"

    # This should raise the original exception after logging
    with pytest.raises(JSONDecodeError):
        await impl._parse_token_response(mock_response)


async def test_token_request_oauth2_error_reraise(hass: HomeAssistant) -> None:
    """Test that OAuth2 errors from _parse_token_response are re-raised."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = "test-client-secret"

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock response where _parse_token_response raises OAuth2TokenRequestError
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 401
    mock_response.text = AsyncMock(return_value='{"error": "invalid_token"}')
    mock_response.json = AsyncMock(return_value={"error": "invalid_token"})
    mock_response.release = MagicMock()
    mock_response.request_info = RequestInfo(
        url=URL("https://example.com/token"),
        method="POST",
        headers={},  # type: ignore[arg-type]
        real_url=URL("https://example.com/token"),
    )
    mock_response.history = ()
    mock_response.headers = {}

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
        pytest.raises(OAuth2TokenRequestReauthError),
    ):
        # The OAuth2TokenRequestReauthError from _raise_token_error should be re-raised
        await impl._token_request({"grant_type": "refresh_token"})


async def test_token_request_without_client_secret_pkce(hass: HomeAssistant) -> None:
    """Test token request without client_secret (PKCE-style OAuth client)."""
    credential = MagicMock()
    credential.client_id = "test-client-id"
    credential.client_secret = None  # PKCE clients don't have a secret

    impl = HeimanOAuth2Implementation(
        hass,
        "heiman_home",
        credential,
        authorization_server=MagicMock(),
    )
    impl.token_url = "https://example.com/token"

    # Mock the session and response
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"access_token": "test-token"})
    mock_response.text = AsyncMock(return_value='{"access_token": "test-token"}')
    mock_response.release = MagicMock()

    mock_session = MagicMock()
    mock_session.post = AsyncMock(return_value=mock_response)

    with (
        patch(
            "homeassistant.components.heiman_home.application_credentials.async_get_clientsession",
            return_value=mock_session,
        ),
    ):
        result = await impl._token_request({"grant_type": "authorization_code"})

        assert result == {"access_token": "test-token"}
        # Verify post was called without auth parameter (auth=None)
        call_args = mock_session.post.call_args
        assert call_args is not None
        # auth should be None when client_secret is None
        assert call_args.kwargs.get("auth") is None
