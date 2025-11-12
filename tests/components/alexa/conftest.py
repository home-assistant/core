"""Fixtures for Alexa integration tests."""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from aiohttp import ClientResponse, ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from custom_components.alexa.const import DOMAIN

# Test data constants
TEST_CLIENT_ID = "amzn1.application-oa2-client.test123"
TEST_CLIENT_SECRET = "test_secret_abc123"
TEST_USER_ID = "amzn1.account.TEST123ABC"
TEST_USER_NAME = "Test User"
TEST_USER_EMAIL = "test@example.com"
TEST_ACCESS_TOKEN = "Atza|IwEBITest123AccessToken"
TEST_REFRESH_TOKEN = "Atzr|IwEBITest123RefreshToken"
TEST_AUTH_CODE = "ANTest123AuthCode"
TEST_FLOW_ID = "test_flow_id_12345"
TEST_VERIFIER = "test_verifier_43chars_aaaaaaaaaaaaaaaaaaaaaa"
TEST_CHALLENGE = "test_challenge_base64url_without_padding"


@pytest.fixture
def mock_hass(tmp_path) -> HomeAssistant:
    """Create a minimal mock Home Assistant instance for testing.

    This fixture provides a lightweight HomeAssistant instance with only
    the necessary attributes for OAuth2 testing. For full integration tests,
    use the hass fixture instead.
    """
    hass = Mock(spec=HomeAssistant)

    # Setup data storage
    hass.data = {DOMAIN: {"pkce": {}}}

    # Setup config
    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    hass.config = Mock()
    hass.config.config_dir = str(config_dir)
    hass.config.path = lambda *args: str(config_dir / (args[0] if args else ""))

    # Setup config_entries manager
    hass.config_entries = Mock()
    hass.config_entries._entries = {}
    hass.config_entries.async_entries = lambda domain=None: [
        e for e in hass.config_entries._entries.values()
        if domain is None or e.domain == domain
    ]
    hass.config_entries.async_get_entry = lambda entry_id: (
        hass.config_entries._entries.get(entry_id)
    )
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

    return hass


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Create a mock ConfigEntry for testing.

    Returns a ConfigEntry with realistic Alexa OAuth data including tokens,
    user profile, and client credentials.
    """
    return ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title=f"Amazon Alexa ({TEST_USER_NAME})",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
                "expires_at": time.time() + 3600,
            },
            "user_id": TEST_USER_ID,
            "name": TEST_USER_NAME,
            "email": TEST_USER_EMAIL,
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        },
        source="user",
        entry_id="test_entry_id_123",
        unique_id=TEST_USER_ID,
        discovery_keys={},
        options={},
        subentries_data=[],
    )


@pytest.fixture
def mock_expired_config_entry() -> ConfigEntry:
    """Create a mock ConfigEntry with expired token for testing reauth."""
    return ConfigEntry(
        version=1,
        minor_version=0,
        domain=DOMAIN,
        title=f"Amazon Alexa ({TEST_USER_NAME})",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": TEST_ACCESS_TOKEN,
                "refresh_token": TEST_REFRESH_TOKEN,
                "expires_in": 3600,
                "token_type": "Bearer",
                "expires_at": time.time() - 3600,  # Expired 1 hour ago
            },
            "user_id": TEST_USER_ID,
            "name": TEST_USER_NAME,
            "email": TEST_USER_EMAIL,
            CONF_CLIENT_ID: TEST_CLIENT_ID,
            CONF_CLIENT_SECRET: TEST_CLIENT_SECRET,
        },
        source="user",
        entry_id="test_entry_id_expired",
        unique_id=TEST_USER_ID,
        discovery_keys={},
        options={},
        subentries_data=[],
    )


@pytest.fixture
def mock_amazon_profile() -> dict[str, Any]:
    """Mock Amazon user profile response."""
    return {
        "user_id": TEST_USER_ID,
        "name": TEST_USER_NAME,
        "email": TEST_USER_EMAIL,
    }


@pytest.fixture
def mock_amazon_token_response() -> dict[str, Any]:
    """Mock Amazon token exchange response."""
    return {
        "access_token": TEST_ACCESS_TOKEN,
        "refresh_token": TEST_REFRESH_TOKEN,
        "expires_in": 3600,
        "token_type": "Bearer",
    }


@pytest.fixture
def mock_amazon_refresh_response() -> dict[str, Any]:
    """Mock Amazon token refresh response."""
    return {
        "access_token": "Atza|NewAccessToken123",
        "expires_in": 3600,
        "token_type": "Bearer",
    }


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession for API calls.

    Provides a mock session with configurable responses for testing
    Amazon API interactions without real HTTP calls.
    """
    session = Mock(spec=ClientSession)

    # Mock response object
    mock_response = Mock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock()
    mock_response.text = AsyncMock(return_value="")

    # Mock context manager for session.get/post
    mock_response.__aenter__ = AsyncMock(return_value=mock_response)
    mock_response.__aexit__ = AsyncMock(return_value=None)

    # For async context manager usage (async with session.get(...)):
    # Return the mock_response directly (it has __aenter__/__aexit__)
    session.get = Mock(return_value=mock_response)

    # For direct await usage (await session.post(...)):
    # Return an AsyncMock that returns mock_response
    session.post = AsyncMock(return_value=mock_response)

    return session, mock_response


@pytest.fixture
def mock_oauth_implementation():
    """Mock OAuth implementation for testing."""
    from custom_components.alexa.oauth import AlexaOAuth2Implementation

    with patch.object(
        AlexaOAuth2Implementation,
        "__init__",
        return_value=None,
    ) as mock_init:
        impl = Mock(spec=AlexaOAuth2Implementation)
        impl.client_id = TEST_CLIENT_ID
        impl.client_secret = TEST_CLIENT_SECRET
        impl.name = "Amazon Alexa"
        impl.domain = DOMAIN
        impl.authorize_url = "https://www.amazon.com/ap/oa"
        impl.token_url = "https://api.amazon.com/auth/o2/token"
        impl.redirect_uri = "http://localhost:8123/auth/external/callback"

        # Mock methods
        impl.async_generate_authorize_url = AsyncMock(
            return_value=f"https://www.amazon.com/ap/oa?client_id={TEST_CLIENT_ID}"
        )
        impl.async_resolve_external_data = AsyncMock()
        impl._async_refresh_token = AsyncMock()

        yield impl


@pytest.fixture
async def setup_integration(mock_hass, mock_config_entry):
    """Set up the Alexa integration for testing.

    This fixture handles the complete integration setup including:
    - OAuth implementation registration
    - Config entry setup
    - Session creation
    """
    from custom_components.alexa import async_setup_entry

    # Register mock OAuth implementation
    with patch(
        "custom_components.alexa.config_entry_oauth2_flow.async_get_implementations",
        return_value={},
    ), patch(
        "custom_components.alexa.config_entry_oauth2_flow.async_register_implementation"
    ) as mock_register, patch(
        "custom_components.alexa.config_entry_oauth2_flow.async_get_config_entry_implementation"
    ) as mock_get_impl, patch(
        "custom_components.alexa.config_entry_oauth2_flow.OAuth2Session"
    ) as mock_session_class:

        # Setup mock session
        mock_session = Mock()
        mock_session.async_ensure_token_valid = AsyncMock()
        mock_session_class.return_value = mock_session

        # Setup mock implementation
        mock_impl = Mock()
        mock_impl.client_id = TEST_CLIENT_ID
        mock_impl.client_secret = TEST_CLIENT_SECRET
        mock_get_impl.return_value = mock_impl

        # Setup integration
        result = await async_setup_entry(mock_hass, mock_config_entry)

        yield result, mock_hass, mock_config_entry


@pytest.fixture
def mock_pkce_pair():
    """Mock PKCE verifier and challenge pair."""
    return TEST_VERIFIER, TEST_CHALLENGE


@pytest.fixture
def mock_jwt_encode():
    """Mock JWT encoding function."""
    with patch(
        "custom_components.alexa.oauth._encode_jwt",
        return_value="mock_jwt_state_token"
    ) as mock:
        yield mock


@pytest.fixture
def mock_secrets():
    """Mock secrets module for PKCE generation."""
    with patch(
        "custom_components.alexa.oauth.secrets.token_urlsafe",
        return_value=TEST_VERIFIER
    ) as mock:
        yield mock


@pytest.fixture
def mock_hashlib():
    """Mock hashlib for PKCE challenge generation."""
    mock_digest = Mock()
    mock_digest.digest.return_value = b"test_challenge_bytes_32chars!!"

    with patch(
        "custom_components.alexa.oauth.hashlib.sha256",
        return_value=mock_digest
    ) as mock:
        yield mock


@pytest.fixture
def mock_base64():
    """Mock base64 encoding for PKCE challenge."""
    with patch(
        "custom_components.alexa.oauth.base64.urlsafe_b64encode"
    ) as mock:
        # Return bytes that decode to TEST_CHALLENGE
        mock.return_value = (TEST_CHALLENGE + "==").encode('ascii')
        yield mock
