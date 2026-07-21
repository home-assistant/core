"""End-to-end test of PoolsideClient.async_connect against a real responder.

Runs a real Noise_XX responder (as in test_noise_transport.py) that also
speaks the post-handshake protocol far enough to answer Device.getStatus,
so the full connect sequence - handshake, ready, initial status fetch - is
exercised together rather than mocked piece by piece.
"""

import json
from typing import Any

from aiohttp import web
from noise.connection import Keypair, NoiseConnection
import pytest

from homeassistant.components.poolside.client import PoolsideClient
from homeassistant.components.poolside.const import NOISE_PROLOGUE, NOISE_PROTOCOL_NAME
from homeassistant.components.poolside.noise_transport import generate_keypair

from tests.typing import ClientSessionGenerator

CONTROLLER_UUID = "controller-1"
STATUS_ITEMS = [
    {
        "UUID": "control-1",
        "name": "ActualPowerState",
        "value": "ON",
        "updated": "2026-01-01T00:00:00Z",
    },
    {
        "UUID": "control-1",
        "name": "PowerState",
        "value": "ON",
        "updated": "2026-01-01T00:00:00Z",
    },
]


@pytest.fixture(autouse=True)
def enable_sockets(socket_enabled: None) -> None:
    """Allow these tests to open the real loopback socket used by the test server."""


def _frame(record: bytes) -> bytes:
    """Frame a single Noise record with its 2-byte big-endian length prefix."""
    return len(record).to_bytes(2, "big") + record


def _split(data: bytes) -> list[bytes]:
    """Split a framed message into its individual records."""
    records = []
    pos = 0
    while pos < len(data):
        length = int.from_bytes(data[pos : pos + 2], "big")
        pos += 2
        records.append(data[pos : pos + length])
        pos += length
    return records


def _make_controller_app(server_private_key: bytes) -> web.Application:
    """Build an app that completes the handshake, sends ready, then answers getStatus."""

    async def handler(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        conn = NoiseConnection.from_name(NOISE_PROTOCOL_NAME)
        conn.set_as_responder()
        conn.set_keypair_from_private_bytes(Keypair.STATIC, server_private_key)
        conn.set_prologue(NOISE_PROLOGUE)
        conn.start_handshake()

        msg1 = _split(await ws.receive_bytes())[0]
        conn.read_message(msg1)
        await ws.send_bytes(_frame(bytes(conn.write_message())))

        msg3 = _split(await ws.receive_bytes())[0]
        conn.read_message(msg3)
        assert conn.handshake_finished

        async def send_json(payload: dict[str, Any]) -> None:
            data = json.dumps(payload).encode()
            await ws.send_bytes(_frame(conn.encrypt(data)))

        async def recv_json() -> dict[str, Any]:
            data = await ws.receive_bytes()
            plaintext = b"".join(conn.decrypt(record) for record in _split(data))
            return json.loads(plaintext)

        await send_json({"type": "ready", "controllerUuid": CONTROLLER_UUID})

        request_msg = await recv_json()
        assert request_msg["method"] == "Device.getStatus"
        await send_json(
            {"id": request_msg["id"], "jsonrpc": "2.0", "result": STATUS_ITEMS}
        )

        # Stay open until the client disconnects, then let the handler end.
        await ws.receive()
        return ws

    app = web.Application()
    app.router.add_get("/", handler)
    return app


async def test_async_connect_fetches_full_status_snapshot(
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """Connecting immediately calls Device.getStatus and populates every control."""
    client_private, _client_public = generate_keypair()
    server_private, server_public = generate_keypair()

    app = _make_controller_app(server_private)
    test_client = await aiohttp_client(app)
    assert test_client.port is not None

    client = PoolsideClient(
        session=test_client.session,
        host=test_client.host,
        port=test_client.port,
        client_private_key=client_private,
        controller_public_key=server_public,
        controller_uuid=CONTROLLER_UUID,
    )
    try:
        await client.async_connect()

        assert client.available
        assert client.get_status("control-1", "ActualPowerState") == "ON"
        assert client.get_status("control-1", "PowerState") == "ON"
    finally:
        await client.async_disconnect()
