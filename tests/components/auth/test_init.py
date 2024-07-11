"""Integration tests for the auth component."""

from datetime import timedelta
from http import HTTPStatus
import logging
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.auth import InvalidAuthError
from homeassistant.auth.models import (
    TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    TOKEN_TYPE_NORMAL,
    Credentials,
)
from homeassistant.components import auth
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from . import async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI, MockUser
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture
def mock_credential():
    """Return a mock credential."""
    return Credentials(
        id="mock-credential-id",
        auth_provider_type="insecure_example",
        auth_provider_id=None,
        data={"username": "test-user"},
        is_new=False,
    )


async def async_setup_user_refresh_token(hass):
    """Create a testing user with a connected credential."""
    user = await hass.auth.async_create_user("Test User")

    credential = Credentials(
        id="mock-credential-id",
        auth_provider_type="insecure_example",
        auth_provider_id=None,
        data={"username": "test-user"},
        is_new=False,
    )
    user.credentials.append(credential)

    return await hass.auth.async_create_refresh_token(
        user, CLIENT_ID, credential=credential
    )


async def test_login_new_user_and_trying_refresh_token(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test logging in with new user and refreshing tokens."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={
            "client_id": CLIENT_ID,
            "username": "test-user",
            "password": "test-pass",
        },
    )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    code = step["result"]

    # Exchange code for tokens
    resp = await client.post(
        "/auth/token",
        data={"client_id": CLIENT_ID, "grant_type": "authorization_code", "code": code},
    )

    assert resp.status == HTTPStatus.OK
    tokens = await resp.json()

    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None
    assert tokens["ha_auth_provider"] == "insecure_example"

    # Use refresh token to get more tokens.
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
    )

    assert resp.status == HTTPStatus.OK
    tokens = await resp.json()
    assert "refresh_token" not in tokens
    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None

    # Test using access token to hit API.
    resp = await client.get("/api/")
    assert resp.status == HTTPStatus.UNAUTHORIZED

    resp = await client.get(
        "/api/", headers={"authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status == HTTPStatus.OK


async def test_auth_code_checks_local_only_user(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test local only user cannot exchange auth code for refresh tokens when external."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={
            "client_id": CLIENT_ID,
            "username": "test-user",
            "password": "test-pass",
        },
    )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    code = step["result"]

    # Exchange code for tokens
    with patch(
        "homeassistant.components.auth.async_user_not_allowed_do_auth",
        return_value="User is local only",
    ):
        resp = await client.post(
            "/auth/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "authorization_code",
                "code": code,
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    error = await resp.json()
    assert error["error"] == "access_denied"


def test_auth_code_store_expiration(
    mock_credential, freezer: FrozenDateTimeFactory
) -> None:
    """Test that the auth code store will not return expired tokens."""
    store, retrieve = auth._create_auth_code_store()
    client_id = "bla"
    now = utcnow()

    freezer.move_to(now)
    code = store(client_id, mock_credential)

    freezer.move_to(now + timedelta(minutes=10))
    assert retrieve(client_id, code) is None

    freezer.move_to(now)
    code = store(client_id, mock_credential)

    freezer.move_to(now + timedelta(minutes=9, seconds=59))
    assert retrieve(client_id, code) == mock_credential


def test_auth_code_store_requires_credentials(mock_credential) -> None:
    """Test we require credentials."""
    store, _retrieve = auth._create_auth_code_store()

    with pytest.raises(TypeError):
        store(None, MockUser())

    store(None, mock_credential)


async def test_ws_current_user(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_access_token: str
) -> None:
    """Test the current user command with Home Assistant creds."""
    assert await async_setup_component(hass, "auth", {})

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    user = refresh_token.user
    client = await hass_ws_client(hass, hass_access_token)

    await client.send_json({"id": 5, "type": "auth/current_user"})

    result = await client.receive_json()
    assert result["success"], result

    user_dict = result["result"]

    assert user_dict["name"] == user.name
    assert user_dict["id"] == user.id
    assert user_dict["is_owner"] == user.is_owner
    assert len(user_dict["credentials"]) == 1

    hass_cred = user_dict["credentials"][0]
    assert hass_cred["auth_provider_type"] == "homeassistant"
    assert hass_cred["auth_provider_id"] is None
    assert "data" not in hass_cred


async def test_cors_on_token(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test logging in with new user and refreshing tokens."""
    client = await async_setup_auth(hass, aiohttp_client)

    resp = await client.options(
        "/auth/token",
        headers={
            "origin": "http://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers["Access-Control-Allow-Origin"] == "http://example.com"
    assert resp.headers["Access-Control-Allow-Methods"] == "POST"

    resp = await client.post("/auth/token", headers={"origin": "http://example.com"})
    assert resp.headers["Access-Control-Allow-Origin"] == "http://example.com"


async def test_refresh_token_system_generated(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test that we can get access tokens for system generated user."""
    client = await async_setup_auth(hass, aiohttp_client)
    user = await hass.auth.async_create_system_user("Test System")
    refresh_token = await hass.auth.async_create_refresh_token(user, None)

    resp = await client.post(
        "/auth/token",
        data={
            "client_id": "https://this-is-not-allowed-for-system-users.com/",
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.token,
        },
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result["error"] == "invalid_request"

    resp = await client.post(
        "/auth/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token.token},
    )

    assert resp.status == HTTPStatus.OK
    tokens = await resp.json()
    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None


async def test_refresh_token_different_client_id(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test that we verify client ID."""
    client = await async_setup_auth(hass, aiohttp_client)
    refresh_token = await async_setup_user_refresh_token(hass)

    # No client ID
    resp = await client.post(
        "/auth/token",
        data={"grant_type": "refresh_token", "refresh_token": refresh_token.token},
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result["error"] == "invalid_request"

    # Different client ID
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": "http://example-different.com",
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.token,
        },
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    result = await resp.json()
    assert result["error"] == "invalid_request"

    # Correct
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.token,
        },
    )

    assert resp.status == HTTPStatus.OK
    tokens = await resp.json()
    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None


async def test_refresh_token_checks_local_only_user(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test that we can't refresh token for a local only user when external."""
    client = await async_setup_auth(hass, aiohttp_client)
    refresh_token = await async_setup_user_refresh_token(hass)
    refresh_token.user.local_only = True

    with patch(
        "homeassistant.components.auth.async_user_not_allowed_do_auth",
        return_value="User is local only",
    ):
        resp = await client.post(
            "/auth/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token.token,
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    result = await resp.json()
    assert result["error"] == "access_denied"


async def test_refresh_token_provider_rejected(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
) -> None:
    """Test that we verify client ID."""
    client = await async_setup_auth(hass, aiohttp_client)
    refresh_token = await async_setup_user_refresh_token(hass)

    # Rejected by provider
    with patch(
        "homeassistant.auth.providers.insecure_example.ExampleAuthProvider.async_validate_refresh_token",
        side_effect=InvalidAuthError("Invalid access"),
    ):
        resp = await client.post(
            "/auth/token",
            data={
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token.token,
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    result = await resp.json()
    assert result["error"] == "access_denied"
    assert result["error_description"] == "Invalid access"


@pytest.mark.parametrize(
    ("url", "base_data"), [("/auth/token", {"action": "revoke"}), ("/auth/revoke", {})]
)
async def test_revoking_refresh_token(
    url, base_data, hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test that we can revoke refresh tokens."""
    client = await async_setup_auth(hass, aiohttp_client)
    refresh_token = await async_setup_user_refresh_token(hass)

    # Test that we can create an access token
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.token,
        },
    )

    assert resp.status == HTTPStatus.OK
    tokens = await resp.json()
    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None

    # Revoke refresh token
    resp = await client.post(url, data={**base_data, "token": refresh_token.token})
    assert resp.status == HTTPStatus.OK

    # Old access token should be no longer valid
    assert hass.auth.async_validate_access_token(tokens["access_token"]) is None

    # Test that we no longer can create an access token
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token.token,
        },
    )

    assert resp.status == HTTPStatus.BAD_REQUEST


async def test_ws_long_lived_access_token(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_access_token: str
) -> None:
    """Test generate long-lived access token."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    ws_client = await hass_ws_client(hass, hass_access_token)

    # verify create long-lived access token
    await ws_client.send_json(
        {
            "id": 5,
            "type": "auth/long_lived_access_token",
            "client_name": "GPS Logger",
            "lifespan": 365,
        }
    )

    result = await ws_client.receive_json()
    assert result["success"], result

    long_lived_access_token = result["result"]
    assert long_lived_access_token is not None

    refresh_token = hass.auth.async_validate_access_token(long_lived_access_token)
    assert refresh_token.client_id is None
    assert refresh_token.client_name == "GPS Logger"
    assert refresh_token.client_icon is None


async def test_ws_refresh_tokens(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_access_token: str
) -> None:
    """Test fetching refresh token metadata."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    ws_client = await hass_ws_client(hass, hass_access_token)

    await ws_client.send_json({"id": 5, "type": "auth/refresh_tokens"})

    result = await ws_client.receive_json()
    assert result["success"], result
    assert len(result["result"]) == 1
    token = result["result"][0]
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    assert token["id"] == refresh_token.id
    assert token["type"] == refresh_token.token_type
    assert token["client_id"] == refresh_token.client_id
    assert token["client_name"] == refresh_token.client_name
    assert token["client_icon"] == refresh_token.client_icon
    assert token["created_at"] == refresh_token.created_at.isoformat()
    assert token["is_current"] is True
    assert token["last_used_at"] == refresh_token.last_used_at.isoformat()
    assert token["last_used_ip"] == refresh_token.last_used_ip
    assert token["auth_provider_type"] == "homeassistant"


async def test_ws_delete_refresh_token(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    hass_ws_client: WebSocketGenerator,
    hass_access_token: str,
) -> None:
    """Test deleting a refresh token."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )

    ws_client = await hass_ws_client(hass, hass_access_token)

    # verify create long-lived access token
    await ws_client.send_json(
        {
            "id": 5,
            "type": "auth/delete_refresh_token",
            "refresh_token_id": refresh_token.id,
        }
    )

    result = await ws_client.receive_json()
    assert result["success"], result
    refresh_token = hass.auth.async_get_refresh_token(refresh_token.id)
    assert refresh_token is None


async def test_ws_delete_all_refresh_tokens_error(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    hass_ws_client: WebSocketGenerator,
    hass_access_token: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deleting all refresh tokens, where a revoke callback raises an error."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    # one token already exists
    await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID + "_1", credential=hass_admin_credential
    )

    def cb():
        raise RuntimeError("I'm bad")

    hass.auth.async_register_revoke_token_callback(token.id, cb)

    ws_client = await hass_ws_client(hass, hass_access_token)

    # get all tokens
    await ws_client.send_json({"id": 5, "type": "auth/refresh_tokens"})
    result = await ws_client.receive_json()
    assert result["success"], result

    tokens = result["result"]

    with patch("homeassistant.components.auth.DELETE_CURRENT_TOKEN_DELAY", 0.001):
        await ws_client.send_json(
            {
                "id": 6,
                "type": "auth/delete_all_refresh_tokens",
            }
        )

        caplog.clear()
        result = await ws_client.receive_json()
        assert result, result["success"] is False
        assert result["error"] == {
            "code": "token_removing_error",
            "message": "During removal, an error was raised.",
        }

    records = [
        record
        for record in caplog.records
        if record.msg == "Error during refresh token removal"
    ]
    assert len(records) == 1
    assert records[0].levelno == logging.ERROR
    assert records[0].exc_info and str(records[0].exc_info[1]) == "I'm bad"
    assert records[0].name == "homeassistant.components.auth"

    await hass.async_block_till_done()
    for token in tokens:
        refresh_token = hass.auth.async_get_refresh_token(token["id"])
        assert refresh_token is None


@pytest.mark.parametrize(
    (
        "delete_token_type",
        "delete_current_token",
        "expected_remaining_normal_tokens",
        "expected_remaining_long_lived_tokens",
    ),
    [
        ({}, {}, 0, 0),
        ({"token_type": TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN}, {}, 3, 0),
        ({"token_type": TOKEN_TYPE_NORMAL}, {}, 0, 1),
        ({"token_type": TOKEN_TYPE_NORMAL}, {"delete_current_token": False}, 1, 1),
    ],
)
async def test_ws_delete_all_refresh_tokens(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    hass_ws_client: WebSocketGenerator,
    hass_access_token: str,
    delete_token_type: dict[str:str],
    delete_current_token: dict[str:bool],
    expected_remaining_normal_tokens: int,
    expected_remaining_long_lived_tokens: int,
) -> None:
    """Test deleting all or some refresh tokens."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    # one token already exists
    await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )

    # create a long lived token
    await hass.auth.async_create_refresh_token(
        hass_admin_user,
        f"{CLIENT_ID}_LL",
        client_name="client_ll",
        credential=hass_admin_credential,
        token_type=TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    )

    await hass.auth.async_create_refresh_token(
        hass_admin_user, f"{CLIENT_ID}_1", credential=hass_admin_credential
    )

    ws_client = await hass_ws_client(hass, hass_access_token)

    # get all tokens
    await ws_client.send_json({"id": 5, "type": "auth/refresh_tokens"})
    result = await ws_client.receive_json()
    assert result["success"], result

    with patch("homeassistant.components.auth.DELETE_CURRENT_TOKEN_DELAY", 0.001):
        await ws_client.send_json(
            {
                "id": 6,
                "type": "auth/delete_all_refresh_tokens",
                **delete_token_type,
                **delete_current_token,
            }
        )

        result = await ws_client.receive_json()
        assert result, result["success"]

    await hass.async_block_till_done()
    # We need to enumerate the user since we may remove the token
    # that is used to authenticate the user which will prevent the websocket
    # connection from working
    remaining_tokens_by_type: dict[str, int] = {
        TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN: 0,
        TOKEN_TYPE_NORMAL: 0,
    }
    for refresh_token in hass_admin_user.refresh_tokens.values():
        remaining_tokens_by_type[refresh_token.token_type] += 1

    assert (
        remaining_tokens_by_type[TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN]
        == expected_remaining_long_lived_tokens
    )
    assert (
        remaining_tokens_by_type[TOKEN_TYPE_NORMAL] == expected_remaining_normal_tokens
    )


async def test_ws_sign_path(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, hass_access_token: str
) -> None:
    """Test signing a path."""
    assert await async_setup_component(hass, "auth", {"http": {}})
    ws_client = await hass_ws_client(hass, hass_access_token)

    with patch(
        "homeassistant.components.auth.async_sign_path", return_value="hello_world"
    ) as mock_sign:
        await ws_client.send_json(
            {
                "id": 5,
                "type": "auth/sign_path",
                "path": "/api/hello",
                "expires": 20,
            }
        )

        result = await ws_client.receive_json()
    assert result["success"], result
    assert result["result"] == {"path": "hello_world"}
    assert len(mock_sign.mock_calls) == 1
    hass, path, expires = mock_sign.mock_calls[0][1]
    assert path == "/api/hello"
    assert expires.total_seconds() == 20


async def test_ws_refresh_token_set_expiry(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    hass_ws_client: WebSocketGenerator,
    hass_access_token: str,
) -> None:
    """Test setting expiry of a refresh token."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    assert refresh_token.expire_at is not None
    ws_client = await hass_ws_client(hass, hass_access_token)

    await ws_client.send_json_auto_id(
        {
            "type": "auth/refresh_token_set_expiry",
            "refresh_token_id": refresh_token.id,
            "enable_expiry": False,
        }
    )

    result = await ws_client.receive_json()
    assert result["success"], result
    refresh_token = hass.auth.async_get_refresh_token(refresh_token.id)
    assert refresh_token.expire_at is None

    await ws_client.send_json_auto_id(
        {
            "type": "auth/refresh_token_set_expiry",
            "refresh_token_id": refresh_token.id,
            "enable_expiry": True,
        }
    )

    result = await ws_client.receive_json()
    assert result["success"], result
    refresh_token = hass.auth.async_get_refresh_token(refresh_token.id)
    assert refresh_token.expire_at is not None


async def test_ws_refresh_token_set_expiry_error(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    hass_access_token: str,
) -> None:
    """Test setting expiry of a invalid refresh token returns error."""
    assert await async_setup_component(hass, "auth", {"http": {}})

    ws_client = await hass_ws_client(hass, hass_access_token)

    await ws_client.send_json_auto_id(
        {
            "type": "auth/refresh_token_set_expiry",
            "refresh_token_id": "invalid",
            "enable_expiry": False,
        }
    )

    result = await ws_client.receive_json()
    assert result, result["success"] is False
    assert result["error"] == {
        "code": "invalid_token_id",
        "message": "Received invalid token",
    }
