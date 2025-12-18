"""Tests for the NRGkick API client wrapper."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from nrgkick_api import (
    NRGkickAuthenticationError as LibAuthError,
    NRGkickConnectionError as LibConnectionError,
)
import pytest

from homeassistant.components.nrgkick.api import (
    NRGkickAPI,
    NRGkickApiClientAuthenticationError,
    NRGkickApiClientCommunicationError,
    NRGkickApiClientError,
)
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def mock_session():
    """Mock aiohttp session."""
    session = AsyncMock()
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"test": "data"})
    response.raise_for_status = MagicMock()

    mock_get = MagicMock()
    mock_get.__aenter__ = AsyncMock(return_value=response)
    mock_get.__aexit__ = AsyncMock(return_value=None)

    session.get = MagicMock(return_value=mock_get)

    return session


class TestHAAPIWrapper:
    """Tests for the Home Assistant API wrapper."""

    async def test_api_init(self):
        """Test API initialization."""
        api = NRGkickAPI(
            host="192.168.1.100",
            username="test_user",
            password="test_pass",
            session=AsyncMock(),
        )

        assert api.host == "192.168.1.100"
        # Wrapper delegates to underlying library API
        assert api._api is not None

    async def test_wrapper_converts_auth_error(self, mock_session):
        """Test wrapper converts library auth error to HA exception."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        with (
            patch.object(
                api._api,
                "get_info",
                side_effect=LibAuthError("Auth failed"),
            ),
            pytest.raises(NRGkickApiClientAuthenticationError),
        ):
            await api.get_info()

    async def test_wrapper_converts_connection_error(self, mock_session):
        """Test wrapper converts library connection error to HA exception."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        with (
            patch.object(
                api._api,
                "get_info",
                side_effect=LibConnectionError("Connection failed"),
            ),
            pytest.raises(NRGkickApiClientCommunicationError),
        ):
            await api.get_info()

    async def test_get_info_passes_through(self, mock_session):
        """Test get_info passes through to library with raw mode."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {
            "general": {"device_name": "Test"}
        }

        result = await api.get_info()

        assert result == {"general": {"device_name": "Test"}}
        mock_session.get.assert_called_once()
        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        # Default raw=True for translation support
        assert params == {"raw": "1"}

    async def test_get_info_with_sections(self, mock_session):
        """Test get_info with specific sections and raw mode."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        # Default: raw=True for translation support
        await api.get_info(["general", "network"])

        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        assert params == {"general": "1", "network": "1", "raw": "1"}

    async def test_get_info_raw_disabled(self, mock_session):
        """Test get_info with raw mode disabled."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        await api.get_info(["general"], raw=False)

        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        assert params == {"general": "1"}

    async def test_get_control(self, mock_session):
        """Test get_control API call."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {
            "charging_current": 16.0
        }

        result = await api.get_control()

        assert result == {"charging_current": 16.0}

    async def test_get_values(self, mock_session):
        """Test get_values API call with raw mode (default)."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {
            "powerflow": {"power": {"total": 11000}}
        }

        result = await api.get_values()

        assert result == {"powerflow": {"power": {"total": 11000}}}
        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        # Default raw=True for translation support
        assert params == {"raw": "1"}

    async def test_get_values_with_sections(self, mock_session):
        """Test get_values with specific sections and raw mode."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {
            "general": {"status": 1}
        }

        await api.get_values(["general"])

        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        assert params == {"general": "1", "raw": "1"}

    async def test_get_values_raw_disabled(self, mock_session):
        """Test get_values with raw mode disabled."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)
        mock_session.get.return_value.__aenter__.return_value.json.return_value = {
            "general": {"status": "STANDBY"}
        }

        await api.get_values(["general"], raw=False)

        call_args = mock_session.get.call_args
        params = call_args[1]["params"]
        assert params == {"general": "1"}

    async def test_set_current(self, mock_session):
        """Test set_current API call."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        await api.set_current(16.0)

        call_args = mock_session.get.call_args
        assert call_args[1]["params"] == {"current_set": 16.0}

    async def test_set_charge_pause(self, mock_session):
        """Test set_charge_pause API call."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        await api.set_charge_pause(True)
        call_args = mock_session.get.call_args
        assert call_args[1]["params"] == {"charge_pause": "1"}

        await api.set_charge_pause(False)
        call_args = mock_session.get.call_args
        assert call_args[1]["params"] == {"charge_pause": "0"}

    async def test_set_energy_limit(self, mock_session):
        """Test set_energy_limit API call."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        await api.set_energy_limit(5000)

        call_args = mock_session.get.call_args
        assert call_args[1]["params"] == {"energy_limit": 5000}

    async def test_set_phase_count(self, mock_session):
        """Test set_phase_count API call."""
        api = NRGkickAPI(host="192.168.1.100", session=mock_session)

        await api.set_phase_count(3)

        call_args = mock_session.get.call_args
        assert call_args[1]["params"] == {"phase_count": 3}

    async def test_set_phase_count_invalid(self):
        """Test set_phase_count with invalid value."""
        api = NRGkickAPI(host="192.168.1.100", session=AsyncMock())

        with pytest.raises(ValueError, match="Phase count must be 1, 2, or 3"):
            await api.set_phase_count(4)

    async def test_api_with_auth(self, mock_session):
        """Test API calls with authentication."""
        api = NRGkickAPI(
            host="192.168.1.100",
            username="test_user",
            password="test_pass",
            session=mock_session,
        )

        await api.get_info()

        call_args = mock_session.get.call_args
        auth = call_args[1]["auth"]
        assert auth is not None
        assert auth.login == "test_user"
        assert auth.password == "test_pass"

    async def test_test_connection_success(self, mock_session):
        """Test connection test success."""
        api = NRGkickAPI("192.168.1.100", session=mock_session)
        assert await api.test_connection()

    async def test_test_connection_failure(self, mock_session):
        """Test connection test failure."""
        api = NRGkickAPI("192.168.1.100", session=mock_session)
        mock_session.get.side_effect = aiohttp.ClientError

        with pytest.raises(NRGkickApiClientCommunicationError):
            await api.test_connection()

    async def test_api_timeout(self, mock_session):
        """Test API timeout."""
        api = NRGkickAPI("192.168.1.100", session=mock_session)
        mock_session.get.side_effect = asyncio.TimeoutError

        with pytest.raises(NRGkickApiClientCommunicationError):
            await api.get_info()

    async def test_api_auth_error(self, mock_session):
        """Test API authentication error."""
        api = NRGkickAPI("192.168.1.100", session=mock_session)
        mock_session.get.return_value.__aenter__.return_value.status = 401

        with pytest.raises(NRGkickApiClientAuthenticationError):
            await api.get_info()


class TestExceptionHierarchy:
    """Tests for exception hierarchy."""

    def test_exception_inheritance(self):
        """Test HA exceptions inherit from HomeAssistantError."""
        assert issubclass(NRGkickApiClientError, HomeAssistantError)
        assert issubclass(NRGkickApiClientCommunicationError, NRGkickApiClientError)
        assert issubclass(NRGkickApiClientAuthenticationError, NRGkickApiClientError)

    def test_exception_translation_keys(self):
        """Test exceptions have translation keys."""
        assert NRGkickApiClientError.translation_domain == "nrgkick"
        assert (
            NRGkickApiClientCommunicationError.translation_key == "communication_error"
        )
        assert (
            NRGkickApiClientAuthenticationError.translation_key
            == "authentication_error"
        )
