"""Test the Api."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.cosa.api import Api


@pytest.fixture
def api():
    """Fixture for initializing the Api."""
    return Api("test-username", "test-password")


def test_api_initialization(api) -> None:
    """Test the initialization of the Api."""
    assert api._Api__username == "test-username"
    assert api._Api__password == "test-password"
    assert api._Api__authToken is None


@pytest.mark.asyncio
async def test__async_login_success(api) -> None:
    """Test successful login."""
    with patch.object(
        api,
        "_Api__async_post_without_auth",
        new=AsyncMock(return_value={"authToken": "test-token", "ok": 1}),
    ):
        assert await api._Api__async_login() is True
        assert api._Api__authToken == "test-token"


@pytest.mark.asyncio
async def test__async_login_failure(api) -> None:
    """Test failed login."""
    with patch.object(
        api,
        "_Api__async_post_without_auth",
        new=AsyncMock(return_value={"ok": 0}),
    ):
        assert await api._Api__async_login() is False
        assert api._Api__authToken is None


@pytest.mark.asyncio
async def test_async_connection_status(api) -> None:
    """Test the async connection status."""
    with patch.object(api, "_Api__async_login", new=AsyncMock(return_value=True)):
        assert await api.async_connection_status() is True

    with patch.object(api, "_Api__async_login", new=AsyncMock(return_value=False)):
        assert await api.async_connection_status() is False


@pytest.mark.asyncio
async def test_async_get_endpoints_success(api) -> None:
    """Test successful retrieval of endpoints."""
    with patch.object(
        api,
        "_Api__async_get",
        new=AsyncMock(return_value={"endpoints": ["endpoint1", "endpoint2"]}),
    ):
        endpoints = await api.async_get_endpoints()
        assert endpoints == ["endpoint1", "endpoint2"]


@pytest.mark.asyncio
async def test_async_get_endpoints_failure(api) -> None:
    """Test failed retrieval of endpoints."""
    with patch.object(api, "_Api__async_get", new=AsyncMock(return_value=None)):
        endpoints = await api.async_get_endpoints()
        assert endpoints is None


@pytest.mark.asyncio
async def test_async_set_target_temperatures_success(api) -> None:
    """Test successful setting of target temperatures."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_set_target_temperatures("endpoint1", 20, 18, 16, 22)
        assert result is True


@pytest.mark.asyncio
async def test_async_set_target_temperatures_failure(api) -> None:
    """Test failed setting of target temperatures."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value=None)):
        result = await api.async_set_target_temperatures("endpoint1", 20, 18, 16, 22)
        assert result is False


@pytest.mark.asyncio
async def test_async_disable_success(api) -> None:
    """Test successful disabling of an endpoint."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_disable("endpoint1")
        assert result is True


@pytest.mark.asyncio
async def test_async_disable_failure(api) -> None:
    """Test failed disabling of an endpoint."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value=None)):
        result = await api.async_disable("endpoint1")
        assert result is False


@pytest.mark.asyncio
async def test_async_enable_schedule_success(api) -> None:
    """Test successful enabling of schedule mode."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_enable_schedule("endpoint1")
        assert result is True


@pytest.mark.asyncio
async def test_async_enable_schedule_failure(api) -> None:
    """Test failed enabling of schedule mode."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value=None)):
        result = await api.async_enable_schedule("endpoint1")
        assert result is False


@pytest.mark.asyncio
async def test_async_enable_custom_mode_success(api) -> None:
    """Test successful enabling of custom mode."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value={"ok": 1})):
        result = await api.async_enable_custom_mode("endpoint1")
        assert result is True


@pytest.mark.asyncio
async def test_async_enable_custom_mode_failure(api) -> None:
    """Test failed enabling of custom mode."""
    with patch.object(api, "_Api__async_post", new=AsyncMock(return_value=None)):
        result = await api.async_enable_custom_mode("endpoint1")
        assert result is False


async def test_is_login_timed_out(api) -> None:
    """Test the __is_login_timed_out method."""

    assert (
        api._Api__is_login_timed_out() is True
    ), "Test when __lastSuccessfulCall is None"

    api._Api__lastSuccessfulCall = datetime.now(UTC)
    assert (
        api._Api__is_login_timed_out() is False
    ), "Test when __lastSuccessfulCall is within the timeout delta"

    api._Api__lastSuccessfulCall = datetime.now(UTC) - timedelta(minutes=100)
    assert (
        api._Api__is_login_timed_out() is True
    ), "Test when __lastSuccessfulCall is outside the timeout delta"
