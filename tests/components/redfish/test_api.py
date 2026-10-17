"""Tests for the Redfish API adapter."""

from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest
from redfish.aio import RedfishAuthenticationError, RedfishConnectionError

from homeassistant.components.redfish.api import (
    RedfishApi,
    RedfishAuthError,
    RedfishError,
)
from homeassistant.components.redfish.const import REQUEST_TIMEOUT


def test_api_uses_official_async_client() -> None:
    """Test the API adapter uses the official asynchronous client."""
    session = Mock(spec=aiohttp.ClientSession)

    with patch(
        "homeassistant.components.redfish.api.AsyncRedfishClient"
    ) as client_class:
        RedfishApi(session, "https://bmc.example", "user", "password")

    client_class.assert_called_once_with(
        base_url="https://bmc.example",
        username="user",
        password="password",
        session=session,
        timeout=REQUEST_TIMEOUT,
    )


async def test_api_uses_basic_authentication() -> None:
    """Test the API adapter configures HTTP Basic authentication."""
    session = Mock(spec=aiohttp.ClientSession)
    client = Mock()
    client.login = AsyncMock()
    with patch(
        "homeassistant.components.redfish.api.AsyncRedfishClient",
        return_value=client,
    ):
        api = RedfishApi(session, "https://bmc.example", "user", "password")

    await api.async_login()

    client.login.assert_awaited_once_with(auth="basic")


async def test_api_posts_reset_with_official_client() -> None:
    """Test reset operations use the official client and exact payload."""
    session = Mock(spec=aiohttp.ClientSession)
    response = Mock(status=204)
    client = Mock()
    client.post = AsyncMock(return_value=response)
    with patch(
        "homeassistant.components.redfish.api.AsyncRedfishClient",
        return_value=client,
    ):
        api = RedfishApi(session, "https://bmc.example", "user", "password")

    await api.async_reset("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset", "On")

    client.post.assert_awaited_once_with(
        "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
        body={"ResetType": "On"},
    )


@pytest.mark.parametrize(
    ("method", "library_error", "expected_error"),
    [
        pytest.param(
            "login",
            RedfishAuthenticationError(),
            RedfishAuthError,
            id="login-authentication",
        ),
        pytest.param(
            "login",
            RedfishConnectionError(),
            RedfishError,
            id="login-connection",
        ),
        pytest.param(
            "logout",
            RedfishAuthenticationError(),
            RedfishAuthError,
            id="logout-authentication",
        ),
        pytest.param(
            "logout",
            RedfishConnectionError(),
            RedfishError,
            id="logout-connection",
        ),
    ],
)
async def test_api_translates_authentication_lifecycle_errors(
    method: str,
    library_error: Exception,
    expected_error: type[RedfishError],
) -> None:
    """Test authentication lifecycle errors use integration exceptions."""
    session = Mock(spec=aiohttp.ClientSession)
    client = Mock()
    setattr(client, method, AsyncMock(side_effect=library_error))
    with patch(
        "homeassistant.components.redfish.api.AsyncRedfishClient",
        return_value=client,
    ):
        api = RedfishApi(session, "https://bmc.example", "user", "password")

    with pytest.raises(expected_error):
        await getattr(api, f"async_{method}")()


async def test_api_translates_reset_authentication_error() -> None:
    """Test reset authentication errors use the integration exception."""
    session = Mock(spec=aiohttp.ClientSession)
    client = Mock()
    client.post = AsyncMock(side_effect=RedfishAuthenticationError)
    with patch(
        "homeassistant.components.redfish.api.AsyncRedfishClient",
        return_value=client,
    ):
        api = RedfishApi(session, "https://bmc.example", "user", "password")

    with pytest.raises(RedfishAuthError):
        await api.async_reset("/redfish/reset", "On")


async def test_api_translates_get_authentication_error() -> None:
    """Test GET authentication errors use the integration exception."""
    session = Mock(spec=aiohttp.ClientSession)
    client = Mock()
    client.get = AsyncMock(side_effect=RedfishAuthenticationError)
    with patch(
        "homeassistant.components.redfish.api.AsyncRedfishClient",
        return_value=client,
    ):
        api = RedfishApi(session, "https://bmc.example", "user", "password")

    with pytest.raises(RedfishAuthError):
        await api.async_get_systems()
