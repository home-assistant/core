"""Tests for the application_credentials platform (PKCE)."""

from unittest.mock import patch

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.components.culiplan.application_credentials import (
    CuliplanOAuth2Implementation,
    async_get_auth_implementation,
    async_get_authorization_server,
)
from homeassistant.components.culiplan.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_SCOPES,
    OAUTH2_TOKEN,
)
from homeassistant.core import HomeAssistant


async def test_authorization_server(hass: HomeAssistant) -> None:
    """Authorization server returns the configured URLs."""
    server = await async_get_authorization_server(hass)
    assert server.authorize_url == OAUTH2_AUTHORIZE
    assert server.token_url == OAUTH2_TOKEN


async def test_auth_implementation_returns_pkce_impl(hass: HomeAssistant) -> None:
    """``async_get_auth_implementation`` returns the PKCE subclass."""
    cred = ClientCredential(client_id="ha-core", client_secret="")
    impl = await async_get_auth_implementation(hass, DOMAIN, cred)
    assert isinstance(impl, CuliplanOAuth2Implementation)


async def test_pkce_extra_authorize_data(hass: HomeAssistant) -> None:
    """``extra_authorize_data`` carries scopes + S256 challenge."""
    cred = ClientCredential(client_id="ha-core", client_secret="")
    server = AuthorizationServer(authorize_url=OAUTH2_AUTHORIZE, token_url=OAUTH2_TOKEN)
    impl = CuliplanOAuth2Implementation(hass, DOMAIN, cred, server)
    extra = impl.extra_authorize_data
    assert extra["code_challenge_method"] == "S256"
    assert extra["code_challenge"]
    assert "openid" in extra["scope"]
    for scope in OAUTH2_SCOPES:
        assert scope in extra["scope"]


async def test_pkce_token_request_injects_verifier(hass: HomeAssistant) -> None:
    """The verifier is injected on the authorization_code exchange."""
    cred = ClientCredential(client_id="ha-core", client_secret="")
    server = AuthorizationServer(authorize_url=OAUTH2_AUTHORIZE, token_url=OAUTH2_TOKEN)
    impl = CuliplanOAuth2Implementation(hass, DOMAIN, cred, server)

    captured: dict[str, str] = {}

    async def fake_super_token_request(data: dict[str, str]) -> dict[str, str]:
        captured.update(data)
        return {"access_token": "x"}

    # Patch the superclass call.
    with patch(
        "homeassistant.components.culiplan.application_credentials"
        ".AuthImplementation._token_request",
        side_effect=fake_super_token_request,
    ):
        await impl._token_request({"grant_type": "authorization_code", "code": "abc"})
    assert captured["code_verifier"] == impl._code_verifier
    captured.clear()

    with patch(
        "homeassistant.components.culiplan.application_credentials"
        ".AuthImplementation._token_request",
        side_effect=fake_super_token_request,
    ):
        await impl._token_request({"grant_type": "refresh_token"})
    assert "code_verifier" not in captured
