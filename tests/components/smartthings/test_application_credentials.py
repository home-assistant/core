"""Test the SmartThings application credentials platform."""

import base64

import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.components.smartthings.app_ledger import async_get_app_ledger
from homeassistant.components.smartthings.application_credentials import (
    SmartThingsOAuth2Implementation,
    async_get_auth_implementation,
)
from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.core import HomeAssistant

TOKEN_URL = "https://auth-global.api.smartthings.com/oauth/token"


async def test_token_request_sends_credentials_as_header(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the token request authenticates with an Authorization header."""
    aioclient_mock.post(TOKEN_URL, json={"access_token": "mock-access-token"})

    implementation = SmartThingsOAuth2Implementation(
        hass,
        DOMAIN,
        ClientCredential("client-id", "client-secret"),
        authorization_server=AuthorizationServer(
            authorize_url="https://api.smartthings.com/oauth/authorize",
            token_url=TOKEN_URL,
        ),
    )

    assert await implementation._token_request({"grant_type": "refresh_token"}) == {
        "access_token": "mock-access-token"
    }

    assert len(aioclient_mock.mock_calls) == 1
    _method, _url, _data, headers = aioclient_mock.mock_calls[0]
    encoded = base64.b64encode(b"client-id:client-secret").decode()
    assert (headers or {}).get("Authorization") == f"Basic {encoded}"


@pytest.mark.parametrize(
    ("auth_domain", "expected_domain"),
    [
        pytest.param(
            f"{DOMAIN}_provisioned-app-id",
            f"{DOMAIN}_provisioned-app-id",
            id="provisioned_app",
        ),
        pytest.param(DOMAIN, DOMAIN, id="imported_credential"),
        pytest.param(f"{DOMAIN}_client_id", DOMAIN, id="ui_credential"),
    ],
)
async def test_auth_implementation_domain(
    hass: HomeAssistant, auth_domain: str, expected_domain: str
) -> None:
    """Test only provisioned apps get their own implementation key.

    Entries set up with other credentials store the legacy DOMAIN key.
    """
    ledger = await async_get_app_ledger(hass)
    await ledger.async_record(
        "provisioned-app-id", "https://example.com/auth/external/callback"
    )

    implementation = await async_get_auth_implementation(
        hass, auth_domain, ClientCredential("client-id", "client-secret")
    )

    assert implementation.domain == expected_domain
