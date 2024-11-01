"""Test auth of websocket API."""

from unittest.mock import patch

import aiohttp
from aiohttp import WSMsgType
import pytest

from homeassistant.auth.providers.homeassistant import HassAuthProvider
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_INVALID,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.const import (
    SIGNAL_WEBSOCKET_CONNECTED,
    SIGNAL_WEBSOCKET_DISCONNECTED,
    URL,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture
def track_connected(hass: HomeAssistant) -> dict[str, list[int]]:
    """Track connected and disconnected events."""
    connected_evt = []

    @callback
    def track_connected():
        connected_evt.append(1)

    async_dispatcher_connect(hass, SIGNAL_WEBSOCKET_CONNECTED, track_connected)
    disconnected_evt = []

    @callback
    def track_disconnected():
        disconnected_evt.append(1)

    async_dispatcher_connect(hass, SIGNAL_WEBSOCKET_DISCONNECTED, track_disconnected)

    return {"connected": connected_evt, "disconnected": disconnected_evt}


async def test_auth_events(
    hass: HomeAssistant,
    no_auth_websocket_client,
    local_auth: HassAuthProvider,
    hass_access_token: str,
    track_connected,
) -> None:
    """Test authenticating."""

    await test_auth_active_with_token(hass, no_auth_websocket_client, hass_access_token)

    assert len(track_connected["connected"]) == 1
    assert not track_connected["disconnected"]

    await no_auth_websocket_client.close()
    await hass.async_block_till_done()

    assert len(track_connected["disconnected"]) == 1


async def test_auth_via_msg_incorrect_pass(no_auth_websocket_client) -> None:
    """Test authenticating."""
    with patch(
        "homeassistant.components.websocket_api.auth.process_wrong_login",
    ) as mock_process_wrong_login:
        await no_auth_websocket_client.send_json(
            {"type": TYPE_AUTH, "api_password": "wrong"}
        )

        msg = await no_auth_websocket_client.receive_json()

    assert mock_process_wrong_login.called
    assert msg["type"] == TYPE_AUTH_INVALID
    assert msg["message"] == "Invalid access token or password"


async def test_auth_events_incorrect_pass(
    no_auth_websocket_client, track_connected
) -> None:
    """Test authenticating."""

    await test_auth_via_msg_incorrect_pass(no_auth_websocket_client)

    assert not track_connected["connected"]
    assert not track_connected["disconnected"]

    await no_auth_websocket_client.close()

    assert not track_connected["connected"]
    assert not track_connected["disconnected"]


async def test_pre_auth_only_auth_allowed(no_auth_websocket_client) -> None:
    """Verify that before authentication, only auth messages are allowed."""
    await no_auth_websocket_client.send_json(
        {
            "type": "call_service",
            "domain": "domain_test",
            "service": "test_service",
            "service_data": {"hello": "world"},
        }
    )

    msg = await no_auth_websocket_client.receive_json()

    assert msg["type"] == TYPE_AUTH_INVALID
    assert msg["message"].startswith("Auth message incorrectly formatted")


async def test_auth_active_with_token(
    hass: HomeAssistant, no_auth_websocket_client, hass_access_token: str
) -> None:
    """Test authenticating with a token."""
    await no_auth_websocket_client.send_json(
        {"type": TYPE_AUTH, "access_token": hass_access_token}
    )
    auth_msg = await no_auth_websocket_client.receive_json()

    assert auth_msg["type"] == TYPE_AUTH_OK


async def test_auth_active_user_inactive(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test authenticating with a token."""
    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    refresh_token.user.is_active = False
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_json({"type": TYPE_AUTH, "access_token": hass_access_token})

        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_INVALID


async def test_auth_active_with_password_not_allow(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test authenticating with a token."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_json({"type": TYPE_AUTH, "api_password": "some-password"})

        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_INVALID


async def test_auth_legacy_support_with_password(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    local_auth: HassAuthProvider,
) -> None:
    """Test authenticating with a token."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_json({"type": TYPE_AUTH, "api_password": "some-password"})

        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_INVALID


async def test_auth_with_invalid_token(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test authenticating with a token."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_json({"type": TYPE_AUTH, "access_token": "incorrect"})

        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_INVALID


async def test_auth_close_after_revoke(
    hass: HomeAssistant, websocket_client, hass_access_token: str
) -> None:
    """Test that a websocket is closed after the refresh token is revoked."""
    assert not websocket_client.closed

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    hass.auth.async_remove_refresh_token(refresh_token)

    msg = await websocket_client.receive()
    assert msg.type is aiohttp.WSMsgType.CLOSE
    assert websocket_client.closed


async def test_auth_sending_invalid_json_disconnects(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test sending invalid json during auth."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_str("[--INVALID--JSON--]")

        auth_msg = await ws.receive()
        assert auth_msg.type == WSMsgType.close


async def test_auth_sending_binary_disconnects(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test sending bytes during auth."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.send_bytes(b"[INVALID]")

        auth_msg = await ws.receive()
        assert auth_msg.type == WSMsgType.close


async def test_auth_close_disconnects(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test closing during auth."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws.close()

        auth_msg = await ws.receive()
        assert auth_msg.type == WSMsgType.CLOSED


async def test_auth_sending_unknown_type_disconnects(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test sending unknown type during auth."""
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    async with client.ws_connect(URL) as ws:
        auth_msg = await ws.receive_json()
        assert auth_msg["type"] == TYPE_AUTH_REQUIRED

        await ws._writer._send_frame(b"1" * 130, 0x30)
        auth_msg = await ws.receive()
        assert auth_msg.type == WSMsgType.close
