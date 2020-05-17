"""Test openid auth provider."""
from datetime import datetime, timezone

from asynctest import patch
from jose import jwt
import pytest

from homeassistant import data_entry_flow
from homeassistant.auth import auth_manager_from_config
from homeassistant.helpers.config_entry_oauth2_flow import _encode_jwt
from homeassistant.setup import async_setup_component

CONST_CLIENT_ID = "123client_id456"
CONST_CLIENT_SECRET = "123client_secret456"

CONST_JWKS_URI = "https://jwks.test/jwks"
CONST_JWKS_KEY = "bla"
CONST_JWKS = {"keys": [CONST_JWKS_KEY]}

CONST_AUTHORIZATION_ENDPOINT = "https://openid.test/authorize"
CONST_TOKEN_ENDPOINT = "https://openid.test/authorize"

CONST_DESCRIPTION_URI = "https://openid.test/.well-known/openid-configuration"
CONST_DESCRIPTION = {
    "issuer": "https://openid.test/",
    "jwks_uri": CONST_JWKS_URI,
    "authorization_endpoint": CONST_AUTHORIZATION_ENDPOINT,
    "token_endpoint": CONST_TOKEN_ENDPOINT,
    "token_endpoint_auth_methods_supported": "client_secret_post",
    "id_token_signing_alg_values_supported": ["RS256", "HS256"],
    "scopes_supported": ["openid", "email", "profile"],
    "response_types_supported": "code",
}

CONST_ACCESS_TOKEN = "dummy_access_token"

CONST_NONCE = "dummy_nonce"
CONST_EMAIL = "john.doe@openid.test"

CONST_ID_TOKEN = {
    "iss": "https://openid.test/",
    "sub": "248289761001",
    "aud": CONST_CLIENT_ID,
    "nonce": CONST_NONCE,
    "exp": datetime(2099, 1, 1, tzinfo=timezone.utc).timestamp(),
    "iat": datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp(),
    "name": "John Doe",
    "email": CONST_EMAIL,
}


@pytest.fixture(name="openid_server")
async def openid_server_fixture(hass, aioclient_mock):
    """Mock openid server."""
    aioclient_mock.get(
        CONST_DESCRIPTION_URI, json=CONST_DESCRIPTION,
    )

    aioclient_mock.get(
        CONST_JWKS_URI, json=CONST_JWKS,
    )

    aioclient_mock.post(
        CONST_TOKEN_ENDPOINT,
        json={
            "access_token": CONST_ACCESS_TOKEN,
            "type": "bearer",
            "expires_in": 60,
            "id_token": jwt.encode(
                CONST_ID_TOKEN, CONST_JWKS_KEY, access_token=CONST_ACCESS_TOKEN
            ),
        },
    )


async def test_login_flow_validates(hass, aiohttp_client, openid_server):
    """Test login flow."""
    assert await async_setup_component(hass, "http", {})

    hass.config.external_url = "https://example.com"

    manager = await auth_manager_from_config(
        hass,
        [
            {
                "type": "openid",
                "configuration": CONST_DESCRIPTION_URI,
                "client_id": CONST_CLIENT_ID,
                "client_secret": CONST_CLIENT_SECRET,
                "emails": [CONST_EMAIL],
            }
        ],
        [],
    )
    hass.auth = manager

    with patch("homeassistant.auth.providers.openid.token_hex") as token_hex:
        token_hex.return_value = CONST_NONCE
        result = await manager.login_flow.async_init(("openid", None))

    state = _encode_jwt(hass, {"flow_id": result["flow_id"], "flow_type": "login"})

    assert result["type"] == data_entry_flow.RESULT_TYPE_EXTERNAL_STEP
    assert result["url"] == (
        f"{CONST_AUTHORIZATION_ENDPOINT}?response_type=code&client_id={CONST_CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}&scope=email+openid+profile&nonce={CONST_NONCE}"
    )

    client = await aiohttp_client(hass.http.app)
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await manager.login_flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"]["email"] == CONST_EMAIL
