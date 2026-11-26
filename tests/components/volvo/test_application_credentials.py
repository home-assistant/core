"""Test the Volvo application credentials."""

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from volvocarsapi.auth import LEGACY_VOLVOID_SERVER, VOLVOID_SERVER

from homeassistant.components.application_credentials import ClientCredential
from homeassistant.components.volvo.application_credentials import (
    async_get_auth_implementation,
)
from homeassistant.components.volvo.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import CLIENT_ID, CLIENT_SECRET, LEGACY_CLIENT_ID, SERVER_TOKEN_RESPONSE


@pytest.mark.parametrize(
    ("name", "expected_name"),
    [
        pytest.param("My Volvo app", "My Volvo app", id="name"),
        pytest.param(None, CLIENT_ID, id="no_name"),
    ],
)
async def test_implementation_name(
    hass: HomeAssistant, name: str | None, expected_name: str
) -> None:
    """Test that the implementation is named after its credential."""
    implementation = await async_get_auth_implementation(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET, name)
    )

    assert implementation.name == expected_name


@pytest.mark.parametrize(
    ("client_id", "token_url", "expected_data", "expected_headers"),
    [
        pytest.param(
            CLIENT_ID,
            VOLVOID_SERVER.token_url,
            {
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": "mock-refresh-token",
            },
            # base64 of "vid-dc-1234:5678"
            {"Authorization": "Basic dmlkLWRjLTEyMzQ6NTY3OA=="},
            id="client_secret_basic",
        ),
        pytest.param(
            LEGACY_CLIENT_ID,
            LEGACY_VOLVOID_SERVER.token_url,
            {
                "grant_type": "refresh_token",
                "client_id": LEGACY_CLIENT_ID,
                "refresh_token": "mock-refresh-token",
                "client_secret": CLIENT_SECRET,
            },
            {},
            id="client_secret_post",
        ),
    ],
)
async def test_token_auth_method(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    client_id: str,
    token_url: str,
    expected_data: dict[str, str],
    expected_headers: dict[str, str],
) -> None:
    """Test that the client secret is sent the way the Volvo ID server requires."""
    aioclient_mock.post(token_url, json=SERVER_TOKEN_RESPONSE)
    implementation = await async_get_auth_implementation(
        hass, DOMAIN, ClientCredential(client_id, CLIENT_SECRET)
    )

    await implementation.async_refresh_token(
        {"access_token": "mock-access-token", "refresh_token": "mock-refresh-token"}
    )

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == expected_data
    assert aioclient_mock.mock_calls[0][3] == expected_headers
