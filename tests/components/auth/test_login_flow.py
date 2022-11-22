"""Tests for the login flow."""
from http import HTTPStatus
from unittest.mock import patch

from . import async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI


async def test_fetch_auth_providers(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.get("/auth/providers")
    assert resp.status == HTTPStatus.OK
    assert await resp.json() == [
        {"name": "Example", "type": "insecure_example", "id": None}
    ]


async def test_fetch_auth_providers_onboarding(hass, aiohttp_client):
    """Test fetching auth providers."""
    client = await async_setup_auth(hass, aiohttp_client)
    with patch(
        "homeassistant.components.onboarding.async_is_user_onboarded",
        return_value=False,
    ):
        resp = await client.get("/auth/providers")
    assert resp.status == HTTPStatus.BAD_REQUEST
    assert await resp.json() == {
        "message": "Onboarding not finished",
        "code": "onboarding_required",
    }


async def test_cannot_get_flows_in_progress(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client, [])
    resp = await client.get("/auth/login_flow")
    assert resp.status == HTTPStatus.METHOD_NOT_ALLOWED


async def test_invalid_username_password(hass, aiohttp_client):
    """Test we cannot get flows in progress."""
    client = await async_setup_auth(hass, aiohttp_client)
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

    # Incorrect username
    with patch(
        "homeassistant.components.auth.login_flow.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "wrong-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert step["step_id"] == "init"
    assert step["errors"]["base"] == "invalid_auth"

    # Incorrect password
    with patch(
        "homeassistant.components.auth.login_flow.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "wrong-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert step["step_id"] == "init"
    assert step["errors"]["base"] == "invalid_auth"

    # Incorrect username and invalid redirect URI fails on wrong login
    with patch(
        "homeassistant.components.auth.login_flow.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "wrong-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert step["step_id"] == "init"
    assert step["errors"]["base"] == "invalid_auth"


async def test_invalid_redirect_uri(hass, aiohttp_client):
    """Test invalid redirect URI."""
    client = await async_setup_auth(hass, aiohttp_client)
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": "https://some-other-domain.com",
        },
    )
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    with patch(
        "homeassistant.components.auth.indieauth.fetch_redirect_uris", return_value=[]
    ), patch(
        "homeassistant.components.http.ban.process_wrong_login"
    ) as mock_process_wrong_login:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    data = await resp.json()
    assert len(mock_process_wrong_login.mock_calls) == 1

    assert data["message"] == "Invalid redirect URI"


async def test_login_exist_user(hass, aiohttp_client):
    """Test logging in with exist user."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    await hass.auth.async_get_or_create_user(cred)

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

    with patch(
        "homeassistant.components.auth.login_flow.process_success_login"
    ) as mock_process_success_login:
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
    assert step["type"] == "create_entry"
    assert len(step["result"]) > 1
    assert len(mock_process_success_login.mock_calls) == 1


async def test_login_local_only_user(hass, aiohttp_client):
    """Test logging in with local only user."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    user = await hass.auth.async_get_or_create_user(cred)
    await hass.auth.async_update_user(user, local_only=True)

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

    with patch(
        "homeassistant.components.auth.login_flow.async_user_not_allowed_do_auth",
        return_value="User is local only",
    ) as mock_not_allowed_do_auth:
        resp = await client.post(
            f"/auth/login_flow/{step['flow_id']}",
            json={
                "client_id": CLIENT_ID,
                "username": "test-user",
                "password": "test-pass",
            },
        )

    assert resp.status == HTTPStatus.FORBIDDEN
    assert len(mock_not_allowed_do_auth.mock_calls) == 1
    assert await resp.json() == {"message": "Login blocked: User is local only"}


async def test_login_exist_user_ip_changes(hass, aiohttp_client):
    """Test logging in and the ip address changes results in an rejection."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    cred = await hass.auth.auth_providers[0].async_get_or_create_credentials(
        {"username": "test-user"}
    )
    await hass.auth.async_get_or_create_user(cred)

    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", None],
            "redirect_uri": CLIENT_REDIRECT_URI,
        },
    )
    assert resp.status == 200
    step = await resp.json()

    #
    # Here we modify the ip_address in the context to make sure
    # when ip address changes in the middle of the login flow we prevent logins.
    #
    # This method was chosen because it seemed less likely to break
    # vs patching aiohttp internals to fake the ip address
    #
    for flow_id, flow in hass.auth.login_flow._progress.items():
        assert flow_id == step["flow_id"]
        flow.context["ip_address"] = "10.2.3.1"

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={
            "client_id": CLIENT_ID,
            "redirect_uri": CLIENT_REDIRECT_URI,
            "username": "test-user",
            "password": "test-pass",
        },
    )

    assert resp.status == 400
    response = await resp.json()
    assert response == {"message": "IP address changed"}


async def test_well_known_auth_info(hass, aiohttp_client):
    """Test logging in and the ip address changes results in an rejection."""
    client = await async_setup_auth(hass, aiohttp_client, setup_api=True)
    resp = await client.get(
        "/.well-known/oauth-authorization-server",
    )
    assert resp.status == 200
    assert await resp.json() == {
        "authorization_endpoint": "/auth/authorize",
        "token_endpoint": "/auth/token",
        "revocation_endpoint": "/auth/revoke",
        "response_types_supported": ["code"],
        "service_documentation": "https://developers.home-assistant.io/docs/auth_api",
    }
