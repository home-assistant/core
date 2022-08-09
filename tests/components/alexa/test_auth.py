"""Test Alexa auth endpoints."""
from homeassistant.components.alexa.auth import Auth
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

from .test_common import TEST_TOKEN_URL


async def run_auth_get_access_token(
    hass,
    aioclient_mock,
    expires_in,
    client_id,
    client_secret,
    accept_grant_code,
    refresh_token,
):
    """Do auth and request a new token for tests."""
    aioclient_mock.post(
        TEST_TOKEN_URL,
        json={
            "access_token": "the_access_token",
            "refresh_token": refresh_token,
            "expires_in": expires_in,
        },
    )

    auth = Auth(hass, client_id, client_secret)
    await auth.async_do_auth(accept_grant_code)
    await auth.async_get_access_token()


async def test_auth_get_access_token_expired(hass, aioclient_mock):
    """Test the auth get access token function."""
    client_id = "client123"
    client_secret = "shhhhh"
    accept_grant_code = "abcdefg"
    refresh_token = "refresher"

    await run_auth_get_access_token(
        hass,
        aioclient_mock,
        -5,
        client_id,
        client_secret,
        accept_grant_code,
        refresh_token,
    )

    assert len(aioclient_mock.mock_calls) == 2
    calls = aioclient_mock.mock_calls

    auth_call_json = calls[0][2]
    token_call_json = calls[1][2]

    assert auth_call_json["grant_type"] == "authorization_code"
    assert auth_call_json["code"] == accept_grant_code
    assert auth_call_json[CONF_CLIENT_ID] == client_id
    assert auth_call_json[CONF_CLIENT_SECRET] == client_secret

    assert token_call_json["grant_type"] == "refresh_token"
    assert token_call_json["refresh_token"] == refresh_token
    assert token_call_json[CONF_CLIENT_ID] == client_id
    assert token_call_json[CONF_CLIENT_SECRET] == client_secret


async def test_auth_get_access_token_not_expired(hass, aioclient_mock):
    """Test the auth get access token function."""
    client_id = "client123"
    client_secret = "shhhhh"
    accept_grant_code = "abcdefg"
    refresh_token = "refresher"

    await run_auth_get_access_token(
        hass,
        aioclient_mock,
        555,
        client_id,
        client_secret,
        accept_grant_code,
        refresh_token,
    )

    assert len(aioclient_mock.mock_calls) == 1
    call = aioclient_mock.mock_calls

    auth_call_json = call[0][2]

    assert auth_call_json["grant_type"] == "authorization_code"
    assert auth_call_json["code"] == accept_grant_code
    assert auth_call_json[CONF_CLIENT_ID] == client_id
    assert auth_call_json[CONF_CLIENT_SECRET] == client_secret
