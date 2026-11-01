"""Tests for the link user flow."""

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

from homeassistant.core import HomeAssistant

from . import async_setup_auth

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI
from tests.typing import ClientSessionGenerator


async def async_get_code(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
) -> dict[str, Any]:
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
    flow_payload: dict[str, Any] = {
        "client_id": CLIENT_ID,
        "handler": ["insecure_example", "2nd auth"],
        "redirect_uri": CLIENT_REDIRECT_URI,
        "type": "link_user",
    }
    if code_challenge is not None:
        flow_payload["code_challenge"] = code_challenge
    if code_challenge_method is not None:
        flow_payload["code_challenge_method"] = code_challenge_method

    resp = await client.post("/auth/login_flow", json=flow_payload)
    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    resp = await client.post(
        f"/auth/login_flow/{step['flow_id']}",
        json={
            "client_id": CLIENT_ID,
            "username": "2nd-user",
            "password": "2nd-pass",
        },
    )

    assert resp.status == HTTPStatus.OK
    step = await resp.json()

    return {
        "user": user,
        "code": step["result"],
        "client": client,
        "access_token": access_token,
    }


async def test_link_user(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
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

    assert resp.status == HTTPStatus.OK
    assert len(info["user"].credentials) == 1


async def test_link_user_invalid_client_id(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
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

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert len(info["user"].credentials) == 0


async def test_link_user_invalid_code(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test linking a user to new credentials."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]

    # Link user
    resp = await client.post(
        "/auth/link_user",
        json={"client_id": CLIENT_ID, "code": "invalid"},
        headers={"authorization": f"Bearer {info['access_token']}"},
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert len(info["user"].credentials) == 0


async def test_link_user_invalid_auth(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
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

    assert resp.status == HTTPStatus.UNAUTHORIZED
    assert len(info["user"].credentials) == 0


async def test_link_user_already_linked_same_user(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test linking a user to a credential it's already linked to."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]
    code = info["code"]

    # Link user
    with patch.object(
        hass.auth, "async_get_user_by_credentials", return_value=info["user"]
    ):
        resp = await client.post(
            "/auth/link_user",
            json={"client_id": CLIENT_ID, "code": code},
            headers={"authorization": f"Bearer {info['access_token']}"},
        )

    assert resp.status == HTTPStatus.OK
    # The credential was not added because it saw that it was already linked
    assert len(info["user"].credentials) == 0


async def test_link_user_already_linked_other_user(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test linking a user to a credential already linked to other user."""
    info = await async_get_code(hass, aiohttp_client)
    client = info["client"]
    code = info["code"]

    another_user = await hass.auth.async_create_user(name="Another")

    # Link user
    with patch.object(
        hass.auth, "async_get_user_by_credentials", return_value=another_user
    ):
        resp = await client.post(
            "/auth/link_user",
            json={"client_id": CLIENT_ID, "code": code},
            headers={"authorization": f"Bearer {info['access_token']}"},
        )

    assert resp.status == HTTPStatus.BAD_REQUEST
    # The credential was not added because it saw that it was already linked
    assert len(info["user"].credentials) == 0
    assert len(another_user.credentials) == 0


async def test_link_user_rejects_pkce_code(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator
) -> None:
    """Test linking a user rejects codes issued with PKCE code_challenge."""
    info = await async_get_code(
        hass,
        aiohttp_client,
        code_challenge="E9Melhoa2OwvFrGMTJguCH5rtx647b100_bCcqqqqqq",
        code_challenge_method="S256",
    )
    client = info["client"]
    code = info["code"]

    resp = await client.post(
        "/auth/link_user",
        json={"client_id": CLIENT_ID, "code": code},
        headers={"authorization": f"Bearer {info['access_token']}"},
    )

    assert resp.status == HTTPStatus.BAD_REQUEST
    assert (await resp.json())["message"] == "Invalid code"
    assert len(info["user"].credentials) == 0
