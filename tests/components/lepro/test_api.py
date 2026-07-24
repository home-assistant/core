"""Tests for the Lepro API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.lepro.api import LoproApiClient
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_oauth_session() -> MagicMock:
    """Return a mocked OAuth2 session."""
    session = MagicMock()
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json = AsyncMock()
    session.async_request = AsyncMock(return_value=response)
    return session


@pytest.fixture
def api_client(hass: HomeAssistant, mock_oauth_session: MagicMock) -> LoproApiClient:
    """Return a LoproApiClient with a mocked session."""
    return LoproApiClient(hass, mock_oauth_session, "https://api-us-iot.lepro.com")


async def test_async_get_devices(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test fetching the device list."""
    mock_oauth_session.async_request.return_value.json = AsyncMock(
        return_value={"data": {"list": [{"did": 1, "name": "Light"}]}}
    )

    result = await api_client.async_get_devices()

    assert result == [{"did": 1, "name": "Light"}]
    assert mock_oauth_session.async_request.call_args[0][0] == "GET"
    assert (
        "/devicestate/list/timestamp/"
        in mock_oauth_session.async_request.call_args[0][1]
    )


async def test_async_get_device_state(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test fetching a single device's state."""
    mock_oauth_session.async_request.return_value.json = AsyncMock(
        return_value={"data": {"did": 1, "switch": 1, "brightness": 800}}
    )

    result = await api_client.async_get_device_state(1)

    assert result == {"did": 1, "switch": 1, "brightness": 800}
    url = mock_oauth_session.async_request.call_args[0][1]
    assert "/devicestate/did/1/timestamp/" in url


async def test_async_turn_on(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test turning on a device sends the correct command."""
    await api_client.async_turn_on(42)

    call_kwargs = mock_oauth_session.async_request.call_args[1]
    assert call_kwargs["params"]["did"] == 42
    assert call_kwargs["params"]["type"] == 1
    assert call_kwargs["params"]["val"] == 1


async def test_async_turn_off(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test turning off a device sends the correct command."""
    await api_client.async_turn_off(42)

    call_kwargs = mock_oauth_session.async_request.call_args[1]
    assert call_kwargs["params"]["did"] == 42
    assert call_kwargs["params"]["type"] == 2
    assert call_kwargs["params"]["val"] == 0


async def test_async_set_color(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test setting a device color sends the correct hex value."""
    await api_client.async_set_color(42, (255, 128, 0))

    call_kwargs = mock_oauth_session.async_request.call_args[1]
    assert call_kwargs["params"]["val"] == "#ff8000"
    assert call_kwargs["params"]["type"] == 3


async def test_async_set_color_temp(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test setting a device color temperature."""
    await api_client.async_set_color_temp(42, 4000)

    call_kwargs = mock_oauth_session.async_request.call_args[1]
    assert call_kwargs["params"]["val"] == "4000K"
    assert call_kwargs["params"]["type"] == 4


async def test_async_set_brightness(
    api_client: LoproApiClient,
    mock_oauth_session: MagicMock,
) -> None:
    """Test setting a device brightness."""
    await api_client.async_set_brightness(42, 75)

    call_kwargs = mock_oauth_session.async_request.call_args[1]
    assert call_kwargs["params"]["val"] == 75
    assert call_kwargs["params"]["type"] == 5
