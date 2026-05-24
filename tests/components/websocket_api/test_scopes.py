"""Phase 7 tests for refresh-token scope enforcement on the websocket API."""

from collections.abc import Callable
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.auth.const import GROUP_ID_ADMIN
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_websocket_api(hass: HomeAssistant) -> None:
    """Make sure websocket_api is up before each test runs."""
    assert await async_setup_component(hass, "websocket_api", {})


@pytest.fixture(autouse=True)
def install_sandbox_command(
    hass: HomeAssistant,
) -> Callable[[HomeAssistant, Any, dict[str, Any]], None]:
    """Install a fake ``sandbox_v2/ping`` command for the scope tests."""

    @websocket_api.websocket_command({vol.Required("type"): "sandbox_v2/ping"})
    @websocket_api.async_response
    async def handle_ping(
        hass: HomeAssistant, connection: Any, msg: dict[str, Any]
    ) -> None:
        connection.send_result(msg["id"], {"pong": True})

    websocket_api.async_register_command(hass, handle_ping)
    return handle_ping


async def _make_scoped_token(hass: HomeAssistant, scopes: frozenset[str]) -> str:
    """Create a system user + scoped refresh token; return its access token."""
    admin_group = await hass.auth.async_get_group(GROUP_ID_ADMIN)
    assert admin_group is not None
    user = await hass.auth.async_create_system_user(
        f"Scoped tester {sorted(scopes)}",
        group_ids=[admin_group.id],
    )
    refresh = await hass.auth.async_create_refresh_token(user, scopes=scopes)
    return hass.auth.async_create_access_token(refresh)


async def test_scoped_token_rejects_out_of_scope_command(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A token with `sandbox_v2/` scope cannot call `call_service`."""
    token = await _make_scoped_token(
        hass, frozenset({"sandbox_v2/", "auth/current_user"})
    )
    ws = await hass_ws_client(hass, access_token=token)

    await ws.send_json_auto_id(
        {
            "type": "call_service",
            "domain": "light",
            "service": "turn_on",
            "service_data": {"entity_id": "light.kitchen"},
        }
    )
    msg = await ws.receive_json()

    assert msg["success"] is False
    assert msg["error"]["code"] == websocket_api.ERR_UNAUTHORIZED


async def test_scoped_token_rejects_auth_sign_path(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A sandbox-style scope must not authorize `auth/sign_path`."""
    assert await async_setup_component(hass, "auth", {})
    token = await _make_scoped_token(
        hass, frozenset({"sandbox_v2/", "auth/current_user"})
    )
    ws = await hass_ws_client(hass, access_token=token)

    await ws.send_json_auto_id({"type": "auth/sign_path", "path": "/api/states"})
    msg = await ws.receive_json()

    assert msg["success"] is False
    assert msg["error"]["code"] == websocket_api.ERR_UNAUTHORIZED


async def test_scoped_token_allows_prefix_match(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A `sandbox_v2/` prefix scope authorizes any `sandbox_v2/...` command."""
    token = await _make_scoped_token(
        hass, frozenset({"sandbox_v2/", "auth/current_user"})
    )
    ws = await hass_ws_client(hass, access_token=token)

    await ws.send_json_auto_id({"type": "sandbox_v2/ping"})
    msg = await ws.receive_json()

    assert msg["success"] is True
    assert msg["result"] == {"pong": True}


async def test_scoped_token_allows_exact_match(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """An exact-match scope authorizes that command only."""
    assert await async_setup_component(hass, "auth", {})
    token = await _make_scoped_token(
        hass, frozenset({"sandbox_v2/", "auth/current_user"})
    )
    ws = await hass_ws_client(hass, access_token=token)

    await ws.send_json_auto_id({"type": "auth/current_user"})
    msg = await ws.receive_json()

    assert msg["success"] is True


async def test_unscoped_token_unaffected(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """A token without scopes still goes through the existing perms path."""
    ws = await hass_ws_client(hass)

    await ws.send_json_auto_id({"type": "sandbox_v2/ping"})
    msg = await ws.receive_json()

    # The handler itself is unconditional once permitted; the unscoped admin
    # token must reach it instead of being scope-gated.
    assert msg["success"] is True
