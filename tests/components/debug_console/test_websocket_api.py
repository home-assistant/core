"""Tests for the Debug console websocket API."""

from collections.abc import AsyncGenerator
from typing import Any

from aiohttp import ClientWebSocketResponse
import pytest
from pytest_homeassistant.common import MockUser
from pytest_homeassistant.typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    WebSocketGenerator,
)

from homeassistant.auth.models import (
    TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN,
    TOKEN_TYPE_NORMAL,
)
from homeassistant.components.debug_console.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_VERSION,
)
from homeassistant.components.debug_console.safeguards import async_warning_required
from homeassistant.components.websocket_api import ERR_UNAUTHORIZED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import COMMANDS


@pytest.fixture
async def setup_without_consent(hass: HomeAssistant) -> None:
    """Set up the console without an accepted warning."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


@pytest.fixture
async def external_client(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    aiohttp_client: ClientSessionGenerator,
    request: pytest.FixtureRequest,
    setup_without_consent: None,
    socket_enabled: None,
) -> AsyncGenerator[ClientWebSocketResponse]:
    """Connect with a parameterized external credential or browser origin."""
    client = await aiohttp_client(hass.http.app)
    origin = str(client.make_url("/").origin())
    hass.config.internal_url = origin
    options = request.param
    token = await hass.auth.async_create_refresh_token(
        hass_admin_user,
        client_id=options.get("client_id", f"{origin}/"),
        client_name="Test client",
        token_type=options.get("token_type", TOKEN_TYPE_NORMAL),
    )
    async with client.ws_connect(
        "/api/websocket", origin=options.get("origin", origin)
    ) as websocket:
        assert (await websocket.receive_json())["type"] == "auth_required"
        await websocket.send_json(
            {
                "type": "auth",
                "access_token": hass.auth.async_create_access_token(token),
            }
        )
        assert (await websocket.receive_json())["type"] == "auth_ok"
        yield websocket


@pytest.mark.parametrize("command", COMMANDS)
async def test_requires_admin(
    websocket_client: MockHAClientWebSocket,
    hass_admin_user: MockUser,
    command: dict[str, Any],
) -> None:
    """Test the console is only available to administrators."""
    hass_admin_user.groups = []

    await websocket_client.send_json_auto_id(command)

    msg = await websocket_client.receive_json()
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_UNAUTHORIZED


@pytest.mark.usefixtures("setup_without_consent")
async def test_existing_frontend_can_accept_warning(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    hass_storage: dict[str, Any],
    frontend_ws_client: WebSocketGenerator,
) -> None:
    """The existing frontend payload saves the existing consent version."""
    websocket_client = await frontend_ws_client(hass_admin_user)
    assert async_warning_required(hass, hass_admin_user.id)
    await websocket_client.send_json_auto_id({"type": "debug_console/warning/accept"})
    assert (await websocket_client.receive_json())["success"]
    assert not async_warning_required(hass, hass_admin_user.id)
    assert (
        hass_storage[DOMAIN]["data"][CONF_WARNING_ACCEPTED][hass_admin_user.id][
            "version"
        ]
        == WARNING_VERSION
        == 1
    )


@pytest.mark.parametrize(
    "external_client",
    [
        pytest.param(
            {"client_id": None, "token_type": TOKEN_TYPE_LONG_LIVED_ACCESS_TOKEN},
            id="long-lived-token",
        ),
        pytest.param({"client_id": "https://agent.example/"}, id="agent-oauth-token"),
        pytest.param({"origin": None}, id="no-browser-origin"),
        pytest.param({"origin": "https://agent.example"}, id="external-origin"),
    ],
    indirect=True,
)
async def test_external_clients_cannot_accept_warning(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    external_client: ClientWebSocketResponse,
) -> None:
    """External admin credentials cannot grant their own consent."""
    await external_client.send_json({"id": 1, "type": "debug_console/warning/accept"})
    response = await external_client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == ERR_UNAUTHORIZED
    assert async_warning_required(hass, hass_admin_user.id)


@pytest.mark.usefixtures("setup_without_consent", "socket_enabled")
async def test_external_client_cannot_spoof_frontend_host(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """An external OAuth origin cannot be trusted through a forged Host header."""
    client = await aiohttp_client(hass.http.app)
    hass.config.internal_url = str(client.make_url("/").origin())
    token = await hass.auth.async_create_refresh_token(
        hass_admin_user, "http://agent.example/"
    )
    async with client.ws_connect(
        "/api/websocket",
        headers={"Host": "agent.example"},
        origin="http://agent.example",
    ) as websocket:
        assert (await websocket.receive_json())["type"] == "auth_required"
        await websocket.send_json(
            {
                "type": "auth",
                "access_token": hass.auth.async_create_access_token(token),
            }
        )
        assert (await websocket.receive_json())["type"] == "auth_ok"
        await websocket.send_json({"id": 1, "type": "debug_console/warning/accept"})
        response = await websocket.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == ERR_UNAUTHORIZED
    assert async_warning_required(hass, hass_admin_user.id)
