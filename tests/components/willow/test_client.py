"""Tests for the Willow API client."""

from http import HTTPStatus
from unittest.mock import Mock

from aiohttp import ClientResponseError
import pytest

from homeassistant.components.willow.client import WillowClient
from homeassistant.components.willow.const import GET_DEVICES_URL, GET_PROFILE_URL
from homeassistant.components.willow.exceptions import WillowAuthError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_get_profile_and_devices(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """The client returns the decoded JSON for profile and devices."""
    aioclient_mock.get(GET_PROFILE_URL, json={"id": 1, "username": "garden"})
    aioclient_mock.get(GET_DEVICES_URL, json=[{"sensor_id": "S1"}])

    client = WillowClient(aiohttp_client.async_get_clientsession(hass), "token")

    assert await client.get_profile() == {"id": 1, "username": "garden"}
    assert await client.get_devices() == [{"sensor_id": "S1"}]

    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "Bearer token"


async def test_update_token_changes_authorization(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Updating the token changes the Authorization header sent."""
    aioclient_mock.get(GET_PROFILE_URL, json={})
    client = WillowClient(aiohttp_client.async_get_clientsession(hass), "old")

    client.update_token("new")
    await client.get_profile()

    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "Bearer new"


@pytest.mark.parametrize(
    "status",
    [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN],
)
async def test_auth_errors_map_to_willow_auth_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
) -> None:
    """401/403 responses raise WillowAuthError."""
    aioclient_mock.get(
        GET_PROFILE_URL,
        exc=ClientResponseError(Mock(), (), status=status),
    )
    client = WillowClient(aiohttp_client.async_get_clientsession(hass), "token")

    with pytest.raises(WillowAuthError):
        await client.get_profile()


async def test_other_errors_propagate(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Non-auth HTTP errors propagate to the caller."""
    aioclient_mock.get(
        GET_PROFILE_URL,
        exc=ClientResponseError(Mock(), (), status=HTTPStatus.INTERNAL_SERVER_ERROR),
    )
    client = WillowClient(aiohttp_client.async_get_clientsession(hass), "token")

    with pytest.raises(ClientResponseError):
        await client.get_profile()
