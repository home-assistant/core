"""Test the SmartThings application credentials platform."""

import base64

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.components.smartthings.application_credentials import (
    SmartThingsOAuth2Implementation,
)
from homeassistant.components.smartthings.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.test_util.aiohttp import AiohttpClientMocker

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
