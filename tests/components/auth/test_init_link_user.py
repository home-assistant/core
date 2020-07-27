"""Tests for the link user flow."""
from . import async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI


async def async_get_code(hass, aiohttp_client):
    """Return authorization code for link user tests."""
    config = [
        {
            "name": "Example",
            "type": "insecure_example",
            "users": [
                {"username": "test-user", "password": "test-pass", "name": "Test Name"}
            ],
        },
        {
            "name": "Example",
            "id": "2nd auth",
            "type": "insecure_example",
            "users": [
                {"username": "2nd-user", "password": "2nd-pass", "name": "2nd Name"}
            ],
        },
    ]
    client = await async_setup_auth(hass, aiohttp_client, config)
    user = await hass.auth.async_create_user(name="Hello")
    refresh_token = await hass.auth.async_create_refresh_token(user, CLIENT_ID)
    access_token = hass.auth.async_create_access_token(refresh_token)

    # Now authenticate with the 2nd flow
    resp = await client.post(
        "/auth/login_flow",
        json={
            "client_id": CLIENT_ID,
            "handler": ["insecure_example", "2nd auth"],
            "redirect_uri": CLIENT_REDIRECT_URI,
            "type": "link_user",
        },
    )
    assert resp.status == 200
    step = await resp.json()

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={"client_id": CLIENT_ID, "username": "2nd-user", "password": "2nd-pass"},
    )

    assert resp.status == 200
    step = await resp.json()

    return {
        "user": user,
        "code": step["result"],
        "client": client,
        "access_token": access_token,
    }


async def test_link_user(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]
    code = info["code"]

    # Link user
    resp = await client.post(
        "/auth/link_user",
        json={"client_id": CLIENT_ID, "code": code},
        headers={"authorization": f"Bearer {info['access_token']}"},
    )

    assert resp.status == 200
    assert len(info["user"].credentials) == 1


async def test_link_user_invalid_client_id(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]
    code = info["code"]

    # Link user
    resp = await client.post(
        "/auth/link_user",
        json={"client_id": "invalid", "code": code},
        headers={"authorization": f"Bearer {info['access_token']}"},
    )

    assert resp.status == 400
    assert len(info["user"].credentials) == 0


async def test_link_user_invalid_code(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]

    # Link user
    resp = await client.post(
        "/auth/link_user",
        json={"client_id": CLIENT_ID, "code": "invalid"},
        headers={"authorization": f"Bearer {info['access_token']}"},
    )

    assert resp.status == 400
    assert len(info["user"].credentials) == 0


async def test_link_user_invalid_auth(hass, aiohttp_client):
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]
    code = info["code"]

    # Link user
    resp = await client.post(
        "/auth/link_user",
        json={"client_id": CLIENT_ID, "code": code},
        headers={"authorization": "Bearer invalid"},
    )

    assert resp.status == 401
    assert len(info["user"].credentials) == 0
