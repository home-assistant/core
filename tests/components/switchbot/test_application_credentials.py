"""Test the SwitchBot application credentials platform."""

from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
from switchbot import OAUTH_AUTHORIZE_URL, OAUTH_SCOPE, OAUTH_TOKEN_URL
from yarl import URL

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    MY_AUTH_CALLBACK_PATH,
    async_get_implementations,
)
from homeassistant.setup import async_setup_component


async def test_application_credentials(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test configured credentials are used for authorization and token exchange."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("client-id", "", name="Test client"),
        auth_domain="test-client",
    )

    implementations = await async_get_implementations(hass, DOMAIN)
    assert set(implementations) == {"test-client"}
    implementation = implementations["test-client"]
    assert implementation.name == "Test client"

    authorize_url = URL(await implementation.async_generate_authorize_url("test-flow"))
    assert str(authorize_url.with_query(None)) == f"{OAUTH_AUTHORIZE_URL}/"
    assert authorize_url.query["client_id"] == "client-id"
    assert authorize_url.query["redirect_uri"] == MY_AUTH_CALLBACK_PATH
    assert authorize_url.query["scope"] == OAUTH_SCOPE

    token_response = {"access_token": "access-token", "expires_in": 3600}
    aioclient_mock.post(OAUTH_TOKEN_URL, json=token_response)
    token = await implementation.async_resolve_external_data(
        {"code": "authorization-code", "state": {"redirect_uri": MY_AUTH_CALLBACK_PATH}}
    )

    assert token == token_response
    assert aioclient_mock.mock_calls == [
        (
            "POST",
            URL(OAUTH_TOKEN_URL),
            {
                "grant_type": "authorization_code",
                "code": "authorization-code",
                "redirect_uri": MY_AUTH_CALLBACK_PATH,
                "client_id": "client-id",
            },
            None,
        )
    ]
