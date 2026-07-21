"""Tests for the Poolside pre-auth pairing protocol against a real websocket server."""

from base64 import b64encode
from collections.abc import Callable, Coroutine
from typing import Any

from aiohttp import ClientWebSocketResponse, web
from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.poolside.pairing import (
    PairingApproved,
    PairingPending,
    PairingRejected,
    async_await_pairing_result,
    async_request_pairing,
)

from tests.typing import ClientSessionGenerator

TEST_PUBLIC_KEY = b"\x03" * 32
TEST_CONTROLLER_PUBLIC_KEY = b"\x04" * 32
TEST_CONTROLLER_UUID = "22222222-2222-2222-2222-222222222222"

Responder = Callable[[web.WebSocketResponse, dict[str, Any]], Coroutine[Any, Any, None]]


@pytest.fixture(autouse=True)
def enable_sockets(socket_enabled: None) -> None:
    """Allow these tests to open the real loopback socket used by the test server."""


async def _request_pairing(
    client: TestClient,
) -> tuple[ClientWebSocketResponse, PairingPending | PairingApproved]:
    """Call async_request_pairing against a running test server."""
    assert client.port is not None
    return await async_request_pairing(
        client.session, client.host, client.port, "Home Assistant", TEST_PUBLIC_KEY
    )


def _make_app(responder: Responder) -> web.Application:
    """Build an aiohttp app that runs `responder` against each pair_request."""

    async def handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        message = await ws.receive_json()
        assert message["type"] == "pair_request"
        await responder(ws, message)
        return ws

    app = web.Application()
    app.router.add_get("/", handler)
    return app


async def test_immediate_approval(aiohttp_client: ClientSessionGenerator) -> None:
    """An already-paired client is approved in the first reply."""

    async def responder(ws: web.WebSocketResponse, _message: dict[str, Any]) -> None:
        await ws.send_json(
            {
                "type": "pair_approved",
                "fingerprint": "AB12-CD34-EF56-7890",
                "controllerPublicKey": b64encode(TEST_CONTROLLER_PUBLIC_KEY).decode(),
                "controllerUuid": TEST_CONTROLLER_UUID,
            }
        )

    client = await aiohttp_client(_make_app(responder))
    ws, result = await _request_pairing(client)

    assert ws.closed
    assert isinstance(result, PairingApproved)
    assert result.controller_public_key == TEST_CONTROLLER_PUBLIC_KEY
    assert result.controller_uuid == TEST_CONTROLLER_UUID


async def test_pending_then_approved(aiohttp_client: ClientSessionGenerator) -> None:
    """A pending pairing resolves once the controller sends the final decision."""

    async def responder(ws: web.WebSocketResponse, _message: dict[str, Any]) -> None:
        await ws.send_json(
            {
                "type": "pair_pending",
                "fingerprint": "AB12-CD34-EF56-7890",
                "expiresAt": "2026-01-01T00:00:00Z",
            }
        )
        await ws.send_json(
            {
                "type": "pair_approved",
                "fingerprint": "AB12-CD34-EF56-7890",
                "controllerPublicKey": b64encode(TEST_CONTROLLER_PUBLIC_KEY).decode(),
                "controllerUuid": TEST_CONTROLLER_UUID,
            }
        )

    client = await aiohttp_client(_make_app(responder))
    ws, result = await _request_pairing(client)

    assert isinstance(result, PairingPending)
    assert result.fingerprint == "AB12-CD34-EF56-7890"

    approved = await async_await_pairing_result(ws)
    assert isinstance(approved, PairingApproved)
    assert approved.controller_uuid == TEST_CONTROLLER_UUID
    assert ws.closed


async def test_pending_then_rejected(aiohttp_client: ClientSessionGenerator) -> None:
    """A pending pairing that's rejected raises PairingRejected."""

    async def responder(ws: web.WebSocketResponse, _message: dict[str, Any]) -> None:
        await ws.send_json(
            {
                "type": "pair_pending",
                "fingerprint": "AB12-CD34-EF56-7890",
                "expiresAt": "2026-01-01T00:00:00Z",
            }
        )
        await ws.send_json({"type": "pair_rejected"})

    client = await aiohttp_client(_make_app(responder))
    ws, result = await _request_pairing(client)
    assert isinstance(result, PairingPending)

    with pytest.raises(PairingRejected):
        await async_await_pairing_result(ws)
