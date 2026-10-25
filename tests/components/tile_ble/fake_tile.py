"""A simulated Tile that speaks the TOA protocol as described by node-tile."""

import asyncio
from collections.abc import Callable
import hashlib
import hmac
import os
from typing import Any

from homeassistant.components.tile_ble.toa import TOA_CMD_CHAR_UUID, TOA_RSP_CHAR_UUID

FAKE_MIC = b"\x00\x00\x00\x00"


def _hmac32(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data[:32].ljust(32, b"\x00"), hashlib.sha256).digest()


class FakeTile:
    """The Tile side of the protocol."""

    def __init__(
        self,
        auth_key: bytes,
        *,
        cid: int = 3,
        song_response: int = 0x02,
        song_error: bool = False,
        respond: bool = True,
        truncate_open_channel: bool = False,
        send_noise: bool = False,
    ) -> None:
        """Initialize the fake Tile."""
        self.auth_key = auth_key
        self.cid = cid
        self.song_response = song_response
        self.song_error = song_error
        self.respond = respond
        self.truncate_open_channel = truncate_open_channel
        self.send_noise = send_noise
        self.session_key: bytes | None = None
        self.nonce = 0
        self.songs: list[bytes] = []
        self.closed_by_client = False

    def handle(self, frame: bytes) -> list[bytes]:
        """Handle a frame written by the client and return the notifications."""
        if not self.respond:
            return []
        if self.send_noise:
            # Responses addressed to another client must be ignored.
            return [b"\x00\xff\xff\xff\x00\x15", *self._handle(frame)]
        return self._handle(frame)

    def _handle(self, frame: bytes) -> list[bytes]:
        if frame[0] == 0:
            return self._handle_connectionless(frame[1:5], frame[5], frame[6:])
        assert frame[0] == self.cid
        assert self.session_key is not None
        message, mic = frame[1:-4], frame[-4:]
        self.nonce += 1
        expected = _hmac32(
            self.session_key,
            self.nonce.to_bytes(8, "little") + bytes([1, len(message)]) + message,
        )[:4]
        if mic != expected:
            return [bytes([self.cid, 0x13, 0x01]) + mic + expected + FAKE_MIC]
        if message[0] == 0x12:
            features = b"\x0f\xff\x01"
            return [
                bytes([self.cid, 0x01, 14]) + features + b"\x01\x00\x00\x00" + FAKE_MIC
            ]
        if message[0] == 0x05 and self.song_error:
            return [bytes([self.cid, 0x05, 0x05, 0x05]) + FAKE_MIC]
        if message[0] == 0x05:
            self.songs.append(message[1:])
            return [bytes([self.cid, 0x07, self.song_response]) + FAKE_MIC]
        if message[0] == 0x11:
            self.closed_by_client = True
            return [bytes([self.cid, 0x13, 0x00]) + FAKE_MIC]
        return [bytes([self.cid, 0x05, 0x02, message[0]]) + FAKE_MIC]

    def _handle_connectionless(
        self, token: bytes, command: int, payload: bytes
    ) -> list[bytes]:
        if command == 0x14:
            rand_t = os.urandom(10)
            sres = hmac.new(
                self.auth_key,
                payload.ljust(16, b"\x00") + rand_t.ljust(16, b"\x00"),
                hashlib.sha256,
            ).digest()[4:8]
            return [b"\x00" + token + b"\x15" + rand_t + sres]
        if command == 0x10 and self.truncate_open_channel:
            return [b"\x00" + token + b"\x12"]
        if command == 0x10:
            rand_t = os.urandom(13)
            self.session_key = _hmac32(
                self.auth_key, payload + rand_t + bytes([self.cid]) + token
            )[:16]
            return [b"\x00" + token + bytes([0x12, self.cid]) + rand_t]
        return []


class FakeBleakClient:
    """A BleakClient connected to a FakeTile."""

    def __init__(self, tile: FakeTile) -> None:
        """Initialize the fake client."""
        self.tile = tile
        self.callback: Callable[[Any, bytearray], None] | None = None
        self.disconnected = False

    async def start_notify(
        self, uuid: str, callback: Callable[[Any, bytearray], None]
    ) -> None:
        """Register for notifications."""
        assert uuid == TOA_RSP_CHAR_UUID
        self.callback = callback

    async def write_gatt_char(
        self, uuid: str, data: bytes, response: bool = False
    ) -> None:
        """Deliver a frame to the Tile and schedule its notifications."""
        assert uuid == TOA_CMD_CHAR_UUID
        assert response is False
        assert self.callback is not None
        loop = asyncio.get_running_loop()
        for notification in self.tile.handle(bytes(data)):
            loop.call_soon(self.callback, None, bytearray(notification))

    async def disconnect(self) -> bool:
        """Disconnect."""
        self.disconnected = True
        return True
