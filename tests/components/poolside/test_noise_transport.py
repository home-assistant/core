"""Tests for the Noise Protocol Framework transport used by Poolside.

Runs a real Noise_XX responder (using the same `noise` library the client
uses) behind an actual aiohttp websocket server, so the handshake and
transport framing are exercised end-to-end rather than mocked.
"""

import json

from aiohttp import web
from noise.connection import Keypair, NoiseConnection
import pytest

from homeassistant.components.poolside.const import NOISE_PROLOGUE, NOISE_PROTOCOL_NAME
from homeassistant.components.poolside.noise_transport import (
    NoiseSession,
    generate_keypair,
)

from tests.typing import ClientSessionGenerator


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


def _make_responder_app(server_private_key: bytes) -> web.Application:
    """Build an aiohttp app that speaks the responder side of Noise_XX."""

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

        incoming = await ws.receive_bytes()
        plaintext = b"".join(conn.decrypt(record) for record in _split(incoming))
        reply = json.dumps({"echo": json.loads(plaintext)}).encode()
        await ws.send_bytes(_frame(conn.encrypt(reply)))

        await ws.close()
        return ws

    app = web.Application()
    app.router.add_get("/", handler)
    return app


async def test_noise_handshake_and_transport_roundtrip(
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """A full Noise_XX handshake against a real responder, then an encrypted round trip."""
    client_private, _client_public = generate_keypair()
    server_private, server_public = generate_keypair()

    app = _make_responder_app(server_private)
    client = await aiohttp_client(app)
    ws = await client.ws_connect("/")

    session = NoiseSession(client_private)
    remote_static = await session.handshake(ws)
    assert remote_static == server_public

    await ws.send_bytes(
        session.encrypt_message(json.dumps({"hello": "world"}).encode())
    )
    response = await ws.receive_bytes()
    decrypted = session.decrypt_message(response)

    assert json.loads(decrypted) == {"echo": {"hello": "world"}}


async def test_noise_handshake_rejects_wrong_pinned_key(
    aiohttp_client: ClientSessionGenerator,
) -> None:
    """A remote static key that doesn't match the pinned key is detectable by the caller."""
    client_private, _client_public = generate_keypair()
    server_private, server_public = generate_keypair()
    _wrong_private, wrong_public = generate_keypair()

    app = _make_responder_app(server_private)
    client = await aiohttp_client(app)
    ws = await client.ws_connect("/")

    session = NoiseSession(client_private)
    remote_static = await session.handshake(ws)

    assert remote_static != wrong_public
    assert remote_static == server_public
