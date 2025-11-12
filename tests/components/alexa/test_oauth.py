"""Tests for Alexa integration oauth.py - OAuth2 with PKCE implementation."""

from __future__ import annotations

import base64
import hashlib
from unittest.mock import AsyncMock, Mock, patch

import pytest
from yarl import URL

from custom_components.alexa.const import (
    AMAZON_AUTH_URL,
    AMAZON_TOKEN_URL,
    DOMAIN,
)
from custom_components.alexa.oauth import AlexaOAuth2Implementation

from .conftest import (
    TEST_AUTH_CODE,
    TEST_ACCESS_TOKEN,
    TEST_CHALLENGE,
    TEST_CLIENT_ID,
    TEST_CLIENT_SECRET,
    TEST_FLOW_ID,
    TEST_REFRESH_TOKEN,
    TEST_VERIFIER,
)


class TestAlexaOAuth2ImplementationInit:
    """Test AlexaOAuth2Implementation initialization."""

    def test_init_success(self, mock_hass):
        """Test successful initialization."""
        impl = AlexaOAuth2Implementation(
            mock_hass,
            DOMAIN,
            TEST_CLIENT_ID,
            TEST_CLIENT_SECRET,
        )

        assert impl.hass == mock_hass
        assert impl._domain == DOMAIN
        assert impl.client_id == TEST_CLIENT_ID
        assert impl.client_secret == TEST_CLIENT_SECRET
        assert impl.authorize_url == AMAZON_AUTH_URL
        assert impl.token_url == AMAZON_TOKEN_URL

        # Verify PKCE storage initialized
        assert DOMAIN in mock_hass.data
        assert "pkce" in mock_hass.data[DOMAIN]
        assert isinstance(mock_hass.data[DOMAIN]["pkce"], dict)

    def test_init_creates_domain_data(self, tmp_path):
        """Test init creates domain data if not exists."""
        hass = Mock()
        hass.data = {}  # Empty data

        impl = AlexaOAuth2Implementation(
            hass,
            DOMAIN,
            TEST_CLIENT_ID,
            TEST_CLIENT_SECRET,
        )

        # Verify domain data was created
        assert DOMAIN in hass.data
        assert "pkce" in hass.data[DOMAIN]

    def test_init_preserves_existing_domain_data(self, mock_hass):
        """Test init preserves existing domain data."""
        # Add existing data
        mock_hass.data[DOMAIN]["existing_key"] = "existing_value"

        impl = AlexaOAuth2Implementation(
            mock_hass,
            DOMAIN,
            TEST_CLIENT_ID,
            TEST_CLIENT_SECRET,
        )

        # Verify existing data preserved
        assert mock_hass.data[DOMAIN]["existing_key"] == "existing_value"
        assert "pkce" in mock_hass.data[DOMAIN]


class TestAlexaOAuth2ImplementationProperties:
    """Test AlexaOAuth2Implementation properties."""

    def test_name_property(self, mock_hass):
        """Test name property."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        assert impl.name == "Amazon Alexa"

    def test_domain_property(self, mock_hass):
        """Test domain property."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        assert impl.domain == DOMAIN

    def test_redirect_uri_property(self, mock_hass):
        """Test redirect_uri property calls framework function."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        with patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ) as mock_get_uri:

            redirect_uri = impl.redirect_uri

            mock_get_uri.assert_called_once_with(mock_hass)
            assert redirect_uri == "http://localhost:8123/auth/external/callback"


class TestGeneratePkcePair:
    """Test _generate_pkce_pair method."""

    def test_generate_pkce_pair_structure(self, mock_hass):
        """Test PKCE pair has correct structure."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        verifier, challenge = impl._generate_pkce_pair()

        # Verify verifier is base64url string
        assert isinstance(verifier, str)
        assert len(verifier) >= 43  # RFC 7636 minimum
        assert len(verifier) <= 128  # RFC 7636 maximum

        # Verify challenge is base64url string
        assert isinstance(challenge, str)
        assert len(challenge) > 0
        # Challenge should not have padding
        assert not challenge.endswith("=")

    def test_generate_pkce_pair_deterministic_challenge(self, mock_hass):
        """Test that same verifier produces same challenge."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Mock verifier
        test_verifier = "test_verifier_43_chars_aaaaaaaaaaaaaaaaaaa"

        with patch(
            "custom_components.alexa.oauth.secrets.token_urlsafe",
            return_value=test_verifier,
        ):
            verifier1, challenge1 = impl._generate_pkce_pair()
            verifier2, challenge2 = impl._generate_pkce_pair()

            # Same verifier should produce same challenge
            assert verifier1 == verifier2 == test_verifier
            assert challenge1 == challenge2

    def test_generate_pkce_pair_sha256_challenge(self, mock_hass):
        """Test challenge is SHA256 hash of verifier."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        test_verifier = "known_verifier_43chars_aaaaaaaaaaaaaaaaa"

        with patch(
            "custom_components.alexa.oauth.secrets.token_urlsafe",
            return_value=test_verifier,
        ):
            verifier, challenge = impl._generate_pkce_pair()

            # Manually compute expected challenge
            verifier_bytes = test_verifier.encode("ascii")
            expected_challenge_bytes = hashlib.sha256(verifier_bytes).digest()
            expected_challenge = (
                base64.urlsafe_b64encode(expected_challenge_bytes)
                .decode("ascii")
                .rstrip("=")
            )

            assert challenge == expected_challenge

    def test_generate_pkce_pair_randomness(self, mock_hass):
        """Test that PKCE pairs are random (different each time)."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Generate multiple pairs
        pairs = [impl._generate_pkce_pair() for _ in range(5)]
        verifiers = [v for v, c in pairs]
        challenges = [c for v, c in pairs]

        # All should be unique
        assert len(set(verifiers)) == 5
        assert len(set(challenges)) == 5


class TestAsyncGenerateAuthorizeUrl:
    """Test async_generate_authorize_url method."""

    async def test_generate_authorize_url_success(self, mock_hass):
        """Test successful authorization URL generation."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        with patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ), patch.object(
            impl, "_generate_pkce_pair", return_value=(TEST_VERIFIER, TEST_CHALLENGE)
        ):

            url = await impl.async_generate_authorize_url(TEST_FLOW_ID)

            # Verify URL structure
            assert url.startswith(AMAZON_AUTH_URL)
            parsed = URL(url)

            # Verify required parameters
            assert parsed.query["response_type"] == "code"
            assert parsed.query["client_id"] == TEST_CLIENT_ID
            assert parsed.query["redirect_uri"] == "http://localhost:8123/auth/external/callback"
            assert "state" in parsed.query  # JWT state token
            assert parsed.query["code_challenge"] == TEST_CHALLENGE
            assert parsed.query["code_challenge_method"] == "S256"

    async def test_generate_authorize_url_stores_verifier(self, mock_hass):
        """Test that verifier is stored for later use."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        with patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ), patch.object(
            impl, "_generate_pkce_pair", return_value=(TEST_VERIFIER, TEST_CHALLENGE)
        ):

            await impl.async_generate_authorize_url(TEST_FLOW_ID)

            # Verify verifier was stored
            assert TEST_FLOW_ID in mock_hass.data[DOMAIN]["pkce"]
            assert mock_hass.data[DOMAIN]["pkce"][TEST_FLOW_ID] == TEST_VERIFIER

    async def test_generate_authorize_url_jwt_state(self, mock_hass):
        """Test that state parameter is JWT-encoded."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        redirect_uri = "http://localhost:8123/auth/external/callback"

        with patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value=redirect_uri,
        ), patch.object(
            impl, "_generate_pkce_pair", return_value=(TEST_VERIFIER, TEST_CHALLENGE)
        ), patch(
            "custom_components.alexa.oauth._encode_jwt",
            return_value="mock_jwt_token",
        ) as mock_encode_jwt:

            url = await impl.async_generate_authorize_url(TEST_FLOW_ID)

            # Verify JWT encoding was called with correct data
            mock_encode_jwt.assert_called_once_with(
                mock_hass,
                {"flow_id": TEST_FLOW_ID, "redirect_uri": redirect_uri}
            )

            # Verify JWT token in URL
            parsed = URL(url)
            assert parsed.query["state"] == "mock_jwt_token"


class TestAsyncResolveExternalData:
    """Test async_resolve_external_data method - Token exchange with PKCE."""

    async def test_resolve_external_data_success(
        self, mock_hass, mock_amazon_token_response, mock_aiohttp_session
    ):
        """Test successful token exchange with PKCE verifier."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Store verifier
        mock_hass.data[DOMAIN]["pkce"][TEST_FLOW_ID] = TEST_VERIFIER

        external_data = {
            "code": TEST_AUTH_CODE,
            "state": {
                "flow_id": TEST_FLOW_ID,
                "redirect_uri": "http://localhost:8123/auth/external/callback",
            },
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_token_response)

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ):

            result = await impl.async_resolve_external_data(external_data)

            # Verify token exchange request
            session.post.assert_called_once_with(
                AMAZON_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": TEST_AUTH_CODE,
                    "redirect_uri": "http://localhost:8123/auth/external/callback",
                    "client_id": TEST_CLIENT_ID,
                    "client_secret": TEST_CLIENT_SECRET,
                    "code_verifier": TEST_VERIFIER,  # PKCE verifier
                },
            )

            # Verify result
            assert result == mock_amazon_token_response
            assert result["access_token"] == TEST_ACCESS_TOKEN

    async def test_resolve_external_data_cleans_up_verifier(
        self, mock_hass, mock_amazon_token_response, mock_aiohttp_session
    ):
        """Test that verifier is removed after use."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Store verifier
        mock_hass.data[DOMAIN]["pkce"][TEST_FLOW_ID] = TEST_VERIFIER

        external_data = {
            "code": TEST_AUTH_CODE,
            "state": {
                "flow_id": TEST_FLOW_ID,
                "redirect_uri": "http://localhost:8123/auth/external/callback",
            },
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_token_response)

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ):

            await impl.async_resolve_external_data(external_data)

            # Verify verifier was removed
            assert TEST_FLOW_ID not in mock_hass.data[DOMAIN]["pkce"]

    async def test_resolve_external_data_invalid_state(self, mock_hass):
        """Test error when state is invalid."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Invalid state (not a dict)
        external_data = {
            "code": TEST_AUTH_CODE,
            "state": "invalid_state_string",
        }

        with pytest.raises(ValueError, match="Invalid state"):
            await impl.async_resolve_external_data(external_data)

    async def test_resolve_external_data_missing_flow_id(self, mock_hass):
        """Test error when state missing flow_id."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # State missing flow_id
        external_data = {
            "code": TEST_AUTH_CODE,
            "state": {"redirect_uri": "http://localhost:8123"},
        }

        with pytest.raises(ValueError, match="missing flow_id"):
            await impl.async_resolve_external_data(external_data)

    async def test_resolve_external_data_verifier_not_found(self, mock_hass):
        """Test error when PKCE verifier not found."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Verifier not stored (expired or replay attack)
        external_data = {
            "code": TEST_AUTH_CODE,
            "state": {
                "flow_id": "unknown_flow_id",
                "redirect_uri": "http://localhost:8123/auth/external/callback",
            },
        }

        with pytest.raises(ValueError, match="PKCE verifier not found"):
            await impl.async_resolve_external_data(external_data)

    async def test_resolve_external_data_token_exchange_fails(
        self, mock_hass, mock_aiohttp_session
    ):
        """Test error when token exchange fails."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Store verifier
        mock_hass.data[DOMAIN]["pkce"][TEST_FLOW_ID] = TEST_VERIFIER

        external_data = {
            "code": TEST_AUTH_CODE,
            "state": {
                "flow_id": TEST_FLOW_ID,
                "redirect_uri": "http://localhost:8123/auth/external/callback",
            },
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 400  # Bad request
        mock_response.text = AsyncMock(return_value="invalid_grant")

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ):

            with pytest.raises(ValueError, match="Token exchange failed"):
                await impl.async_resolve_external_data(external_data)

            # Verify verifier was still cleaned up (in finally block)
            assert TEST_FLOW_ID not in mock_hass.data[DOMAIN]["pkce"]


class TestAsyncRefreshToken:
    """Test _async_refresh_token method."""

    async def test_refresh_token_success(
        self, mock_hass, mock_amazon_refresh_response, mock_aiohttp_session
    ):
        """Test successful token refresh."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        token = {
            "refresh_token": TEST_REFRESH_TOKEN,
            "access_token": "old_token",
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_refresh_response)

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ):

            result = await impl._async_refresh_token(token)

            # Verify refresh request
            session.post.assert_called_once_with(
                AMAZON_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": TEST_REFRESH_TOKEN,
                    "client_id": TEST_CLIENT_ID,
                    "client_secret": TEST_CLIENT_SECRET,
                },
            )

            # Verify result
            assert result == mock_amazon_refresh_response
            assert result["access_token"] == "Atza|NewAccessToken123"

    async def test_refresh_token_no_pkce(
        self, mock_hass, mock_amazon_refresh_response, mock_aiohttp_session
    ):
        """Test that refresh does not use PKCE (only for authorization)."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        token = {"refresh_token": TEST_REFRESH_TOKEN}

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_amazon_refresh_response)

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ):

            await impl._async_refresh_token(token)

            # Verify no code_verifier in request
            call_data = session.post.call_args[1]["data"]
            assert "code_verifier" not in call_data
            assert call_data["grant_type"] == "refresh_token"

    async def test_refresh_token_fails(self, mock_hass, mock_aiohttp_session):
        """Test error when token refresh fails."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        token = {"refresh_token": TEST_REFRESH_TOKEN}

        session, mock_response = mock_aiohttp_session
        mock_response.status = 401  # Unauthorized
        mock_response.text = AsyncMock(return_value="invalid_refresh_token")

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ):

            with pytest.raises(ValueError, match="Token refresh failed"):
                await impl._async_refresh_token(token)


class TestPKCESecurityProperties:
    """Test PKCE security properties and RFC 7636 compliance."""

    def test_pkce_verifier_length_compliant(self, mock_hass):
        """Test verifier length is RFC 7636 compliant (43-128 chars)."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        verifier, _ = impl._generate_pkce_pair()

        # RFC 7636 section 4.1: 43 <= length <= 128
        assert 43 <= len(verifier) <= 128

    def test_pkce_challenge_no_padding(self, mock_hass):
        """Test challenge has no padding (RFC 7636 base64url)."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        _, challenge = impl._generate_pkce_pair()

        # RFC 7636 section 4.2: base64url without padding
        assert not challenge.endswith("=")

    async def test_pkce_one_time_use(self, mock_hass, mock_aiohttp_session):
        """Test verifier is one-time use (removed after exchange)."""
        impl = AlexaOAuth2Implementation(
            mock_hass, DOMAIN, TEST_CLIENT_ID, TEST_CLIENT_SECRET
        )

        # Store verifier
        mock_hass.data[DOMAIN]["pkce"][TEST_FLOW_ID] = TEST_VERIFIER

        external_data = {
            "code": TEST_AUTH_CODE,
            "state": {
                "flow_id": TEST_FLOW_ID,
                "redirect_uri": "http://localhost:8123/auth/external/callback",
            },
        }

        session, mock_response = mock_aiohttp_session
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"access_token": "token"})

        with patch(
            "homeassistant.helpers.aiohttp_client.async_get_clientsession",
            return_value=session,
        ), patch(
            "custom_components.alexa.oauth.config_entry_oauth2_flow.async_get_redirect_uri",
            return_value="http://localhost:8123/auth/external/callback",
        ):

            # First use should succeed
            await impl.async_resolve_external_data(external_data)

            # Second use should fail (verifier removed)
            with pytest.raises(ValueError, match="PKCE verifier not found"):
                await impl.async_resolve_external_data(external_data)
