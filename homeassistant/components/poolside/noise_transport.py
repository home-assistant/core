"""Noise Protocol Framework transport for the Poolside controller.

Implements the client side of Noise_XX_25519_ChaChaPoly_SHA256 over the
controller's websocket, plus the record framing used for both the handshake
and the encrypted JSON-RPC transport that follows it.
"""

import hashlib

from aiohttp import ClientWebSocketResponse, WSMsgType
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from noise.connection import Keypair, NoiseConnection

from .const import NOISE_PROLOGUE, NOISE_PROTOCOL_NAME

MAX_PLAINTEXT_CHUNK = 60000
RECORD_LENGTH_BYTES = 2


class NoiseTransportError(Exception):
    """Raised when the Noise handshake or transport framing fails."""


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate a new X25519 static keypair, returning (private_raw, public_raw)."""
    private_key = X25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        serialization.Encoding.Raw,
        serialization.PrivateFormat.Raw,
        serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    return private_raw, public_raw


def public_key_from_private(private_raw: bytes) -> bytes:
    """Derive the raw public key bytes from a raw private key."""
    private_key = X25519PrivateKey.from_private_bytes(private_raw)
    return private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )


def fingerprint(public_raw: bytes) -> str:
    """Return the dash-separated fingerprint shown to the user during pairing."""
    digest = hashlib.sha256(public_raw).hexdigest().upper()[:16]
    return "-".join(digest[i : i + 4] for i in range(0, 16, 4))


def _frame_records(records: list[bytes]) -> bytes:
    """Prefix each record with its 2-byte big-endian length and concatenate."""
    out = bytearray()
    for record in records:
        out += len(record).to_bytes(RECORD_LENGTH_BYTES, "big")
        out += record
    return bytes(out)


def _split_records(data: bytes) -> list[bytes]:
    """Split a framed binary websocket message into its individual records."""
    records: list[bytes] = []
    pos = 0
    total = len(data)
    while pos < total:
        if pos + RECORD_LENGTH_BYTES > total:
            raise NoiseTransportError("Truncated record length header")
        length = int.from_bytes(data[pos : pos + RECORD_LENGTH_BYTES], "big")
        pos += RECORD_LENGTH_BYTES
        if pos + length > total:
            raise NoiseTransportError("Truncated record body")
        records.append(data[pos : pos + length])
        pos += length
    return records


async def _read_binary(ws: ClientWebSocketResponse) -> bytes:
    """Read the next binary websocket message, raising on anything else."""
    msg = await ws.receive()
    if msg.type is not WSMsgType.BINARY:
        raise NoiseTransportError(f"Expected a binary frame, got {msg.type}")
    return msg.data


class NoiseSession:
    """A single Noise_XX session: performs the handshake, then encrypts/decrypts."""

    def __init__(self, private_key: bytes) -> None:
        """Set up the Noise connection as the initiator with our static key."""
        self._conn = NoiseConnection.from_name(NOISE_PROTOCOL_NAME)
        self._conn.set_as_initiator()
        self._conn.set_keypair_from_private_bytes(Keypair.STATIC, private_key)
        self._conn.set_prologue(NOISE_PROLOGUE)
        self._conn.start_handshake()

    async def handshake(self, ws: ClientWebSocketResponse) -> bytes:
        """Run the XX handshake and return the remote static public key."""
        msg1 = bytes(self._conn.write_message())
        await ws.send_bytes(_frame_records([msg1]))

        records = _split_records(await _read_binary(ws))
        if len(records) != 1:
            raise NoiseTransportError(
                f"Expected exactly one record in handshake message 2, got {len(records)}"
            )
        self._conn.read_message(records[0])
        # The server's static key arrives in this message; capture it now,
        # since NoiseProtocol drops its handshake_state once the handshake
        # (the write_message call below) completes.
        remote_static = bytes(self._conn.noise_protocol.handshake_state.rs.public_bytes)

        msg3 = bytes(self._conn.write_message())
        await ws.send_bytes(_frame_records([msg3]))

        if not self._conn.handshake_finished:
            raise NoiseTransportError("Handshake did not complete")

        return remote_static

    def encrypt_message(self, plaintext: bytes) -> bytes:
        """Encrypt a JSON payload into a single framed binary websocket message."""
        chunks = [
            plaintext[i : i + MAX_PLAINTEXT_CHUNK]
            for i in range(0, len(plaintext), MAX_PLAINTEXT_CHUNK)
        ] or [b""]
        records = [self._conn.encrypt(chunk) for chunk in chunks]
        return _frame_records(records)

    def decrypt_message(self, data: bytes) -> bytes:
        """Decrypt a framed binary websocket message back into a JSON payload."""
        records = _split_records(data)
        return b"".join(self._conn.decrypt(record) for record in records)
