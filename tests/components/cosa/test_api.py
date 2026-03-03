"""Test the Cosa API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.cosa.api import (
    CosaApi,
    CosaAuthError,
    CosaConnectionError,
)


@pytest.fixture
def mock_session() -> MagicMock:
    """Return a mocked aiohttp.ClientSession."""
    return MagicMock(spec=aiohttp.ClientSession)


@pytest.fixture
def api(mock_session: MagicMock) -> CosaApi:
    """Return a CosaApi instance with mocked session."""
    return CosaApi("test-user", "test-pass", mock_session)


async def test_check_connection_success(api: CosaApi) -> None:
    """Test successful connection check."""
    with patch.object(api, "_async_login", new=AsyncMock(return_value=None)):
        assert await api.async_check_connection() is True


async def test_check_connection_auth_failure(api: CosaApi) -> None:
    """Test connection check with invalid credentials."""
    with (
        patch.object(
            api,
            "_async_login",
            new=AsyncMock(side_effect=CosaAuthError("Invalid credentials")),
        ),
        pytest.raises(CosaAuthError),
    ):
        await api.async_check_connection()


async def test_check_connection_network_failure(api: CosaApi) -> None:
    """Test connection check with network failure."""
    with (
        patch.object(
            api,
            "_async_login",
            new=AsyncMock(side_effect=CosaConnectionError("Connection refused")),
        ),
        pytest.raises(CosaConnectionError),
    ):
        await api.async_check_connection()


async def test_get_endpoints_success(api: CosaApi) -> None:
    """Test successful retrieval of endpoints."""
    with patch.object(
        api,
        "_async_get",
        new=AsyncMock(return_value={"endpoints": [{"id": "ep1"}, {"id": "ep2"}]}),
    ):
        endpoints = await api.async_get_endpoints()
        assert endpoints == [{"id": "ep1"}, {"id": "ep2"}]


async def test_get_endpoints_empty(api: CosaApi) -> None:
    """Test retrieval of endpoints when none exist."""
    with patch.object(api, "_async_get", new=AsyncMock(return_value=None)):
        endpoints = await api.async_get_endpoints()
        assert endpoints == []


async def test_get_endpoint_success(api: CosaApi) -> None:
    """Test successful retrieval of a single endpoint."""
    endpoint_data = {"id": "ep1", "mode": "manual", "option": "custom"}
    with patch.object(
        api,
        "_async_post",
        new=AsyncMock(return_value={"endpoint": endpoint_data}),
    ):
        result = await api.async_get_endpoint("ep1")
        assert result == endpoint_data


async def test_get_endpoint_failure(api: CosaApi) -> None:
    """Test failed retrieval of a single endpoint."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value=None)):
        result = await api.async_get_endpoint("ep1")
        assert result is None


async def test_set_target_temperatures_success(api: CosaApi) -> None:
    """Test successful setting of target temperatures."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_set_target_temperatures("ep1", 22, 18, 19, 25)
        assert result is True


async def test_set_target_temperatures_failure(api: CosaApi) -> None:
    """Test failed setting of target temperatures."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value=None)):
        result = await api.async_set_target_temperatures("ep1", 22, 18, 19, 25)
        assert result is False


async def test_disable_success(api: CosaApi) -> None:
    """Test successful disabling of an endpoint."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_disable("ep1")
        assert result is True


async def test_disable_failure(api: CosaApi) -> None:
    """Test failed disabling of an endpoint."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value=None)):
        result = await api.async_disable("ep1")
        assert result is False


async def test_enable_schedule_success(api: CosaApi) -> None:
    """Test successful enabling of schedule mode."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_enable_schedule("ep1")
        assert result is True


async def test_enable_schedule_failure(api: CosaApi) -> None:
    """Test failed enabling of schedule mode."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value=None)):
        result = await api.async_enable_schedule("ep1")
        assert result is False


async def test_enable_custom_mode_success(api: CosaApi) -> None:
    """Test successful enabling of custom mode."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_enable_custom_mode("ep1")
        assert result is True


async def test_enable_custom_mode_failure(api: CosaApi) -> None:
    """Test failed enabling of custom mode."""
    with patch.object(api, "_async_post", new=AsyncMock(return_value=None)):
        result = await api.async_enable_custom_mode("ep1")
        assert result is False
