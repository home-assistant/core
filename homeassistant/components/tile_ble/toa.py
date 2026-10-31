"""Tile Over-the-Air (TOA) protocol, used to ring a Tile over Bluetooth.

The protocol is undocumented; this follows node-tile
(https://github.com/lesleyxyz/node-tile, MIT, Copyright (c) 2024 Lesley De Keyser).
"""

import asyncio
import base64
import binascii
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from enum import IntEnum
import hashlib
import hmac
import logging
import os

from bleak import BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection

_LOGGER = logging.getLogger(__name__)


TOA_CMD_CHAR_UUID = "9d410018-35d6-f4dd-ba60-e7bd8dc491c0"
TOA_RSP_CHAR_UUID = "9d410019-35d6-f4dd-ba60-e7bd8dc491c0"

CONNECTIONLESS_CID = 0
AUTH_KEY_LEN = 16
SESSION_KEY_LEN = 16
TOKEN_LEN = 4
RAND_A_LEN = 14
RAND_T_LEN = 13
MIC_LEN = 4

# Maximum payload size the client announces in its READY command.
CLIENT_MPS = 0x13

TILE_SONG_FIND = 0x01

RESPONSE_TIMEOUT = 10.0

_HMAC_INPUT_LEN = 32


class ToaCommand(IntEnum):
    """Commands sent by the client."""

    SONG = 0x05
    OPEN_CHANNEL = 0x10
    CLOSE_CHANNEL = 0x11
    READY = 0x12
    AUTHENTICATE = 0x14


class ToaResponse(IntEnum):
    """Responses sent by the Tile."""

    READY = 0x01
    ERROR = 0x05
    SONG = 0x07
    OPEN_CHANNEL = 0x12
    CLOSE_CHANNEL = 0x13
    AUTHENTICATE = 0x15


class SongCommand(IntEnum):
    """Song sub-commands."""

    PLAY = 0x02


class SongResponse(IntEnum):
    """Song sub-responses."""

    PLAY_OK = 0x02
    ERROR = 0x20


class CloseReason(IntEnum):
    """Reasons the Tile gives for closing a channel."""

    NO_ERROR = 0x00
    MIC_FAILURE = 0x01
    TKA_MISSING = 0x02
    BROADCAST_MIC_FAILURE = 0x03


class TileVolume(IntEnum):
    """Volume used when ringing a Tile."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3


class TileBleError(Exception):
    """Base exception for talking to a Tile over Bluetooth."""


class TileBleConnectionError(TileBleError):
    """Raised when the Tile cannot be reached or does not respond."""


class TileBleAuthenticationError(TileBleError):
    """Raised when the Tile rejects the auth key."""


@dataclass(frozen=True, slots=True)
class ToaMessage:
    """A response received from the Tile."""

    code: int
    payload: bytes


def _hmac_sha256(key: bytes, *parts: bytes) -> bytes:
    """Return HMAC-SHA256 over the parts, zero-padded or truncated to 32 bytes."""
    data = b"".join(parts)[:_HMAC_INPUT_LEN].ljust(_HMAC_INPUT_LEN, b"\x00")
    return hmac.new(key, data, hashlib.sha256).digest()


def decode_auth_key(auth_key: str) -> bytes:
    """Decode the base64 auth key provided by the Tile cloud API."""
    try:
        key = base64.b64decode(auth_key, validate=True)
    except binascii.Error as err:
        raise ValueError("Auth key is not valid base64") from err
    if len(key) != AUTH_KEY_LEN:
        raise ValueError(f"Auth key must be {AUTH_KEY_LEN} bytes, got {len(key)}")
    return key


def compute_sres(auth_key: bytes, rand_a: bytes, rand_t: bytes) -> bytes:
    """Return the SRES the Tile sends in its AUTHENTICATE response."""
    data = rand_a.ljust(16, b"\x00") + rand_t.ljust(16, b"\x00")
    return hmac.new(auth_key, data, hashlib.sha256).digest()[4:8]


def derive_session_key(
    auth_key: bytes, rand_a: bytes, rand_t: bytes, cid: int, token: bytes
) -> bytes:
    """Derive the key used to sign messages on an open channel."""
    return _hmac_sha256(auth_key, rand_a, rand_t, bytes([cid]), token)[:SESSION_KEY_LEN]


def compute_mic(session_key: bytes, nonce: int, message: bytes) -> bytes:
    """Return the message integrity code for a channel message."""
    return _hmac_sha256(
        session_key,
        nonce.to_bytes(8, "little"),
        bytes([0x01, len(message)]),
        message,
    )[:MIC_LEN]


def build_connectionless_frame(token: bytes, command: int, payload: bytes) -> bytes:
    """Build a frame for the connectionless channel."""
    return bytes([CONNECTIONLESS_CID]) + token + bytes([command]) + payload


def build_channel_frame(
    cid: int, session_key: bytes, nonce: int, message: bytes
) -> bytes:
    """Build a signed frame for an open channel."""
    return bytes([cid]) + message + compute_mic(session_key, nonce, message)


def parse_connectionless_frame(data: bytes, token: bytes) -> ToaMessage | None:
    """Parse a connectionless response addressed to this client."""
    if len(data) < 6 or data[0] != CONNECTIONLESS_CID or data[1:5] != token:
        return None
    return ToaMessage(data[5], data[6:])


def parse_channel_frame(data: bytes, cid: int) -> ToaMessage | None:
    """Parse a response on an open channel.

    The trailing MIC is stripped but not verified, as the Tile's signing scheme
    for responses is not documented.
    """
    if len(data) < 2 + MIC_LEN or data[0] != cid:
        return None
    return ToaMessage(data[1], data[2:-MIC_LEN])


class _Channel:
    """An authenticated TOA channel on a connected Tile."""

    def __init__(self, client: BleakClient, auth_key: bytes) -> None:
        self._client = client
        self._auth_key = auth_key
        self._token = os.urandom(TOKEN_LEN)
        self._rand_a = os.urandom(RAND_A_LEN)
        self._cid: int | None = None
        self._session_key = b""
        self._nonce = 0
        self._closed = False
        self._waiters: dict[int, asyncio.Future[ToaMessage]] = {}

    def handle_notification(
        self, _characteristic: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        """Dispatch a response from the Tile to the request waiting for it."""
        frame = bytes(data)
        if self._cid is None:
            message = parse_connectionless_frame(frame, self._token)
        else:
            message = parse_channel_frame(frame, self._cid)
        if message is None:
            return

        if message.code == ToaResponse.CLOSE_CHANNEL:
            self._closed = True
            reason = message.payload[0] if message.payload else None
            if reason == CloseReason.MIC_FAILURE:
                self._fail_waiters(
                    TileBleAuthenticationError("The Tile rejected the auth key")
                )
            else:
                self._fail_waiters(
                    TileBleError(f"The Tile closed the channel: {reason}")
                )
            return
        if message.code == ToaResponse.ERROR:
            self._fail_waiters(
                TileBleError(f"The Tile returned an error: {message.payload.hex()}")
            )
            return

        if (waiter := self._waiters.pop(message.code, None)) and not waiter.done():
            waiter.set_result(message)

    def _fail_waiters(self, err: TileBleError) -> None:
        for waiter in self._waiters.values():
            if not waiter.done():
                waiter.set_exception(err)
        self._waiters.clear()

    async def _send(self, frame: bytes, response: ToaResponse) -> ToaMessage:
        waiter: asyncio.Future[ToaMessage] = asyncio.get_running_loop().create_future()
        self._waiters[response] = waiter
        try:
            await self._client.write_gatt_char(TOA_CMD_CHAR_UUID, frame, response=False)
            async with asyncio.timeout(RESPONSE_TIMEOUT):
                return await waiter
        except TimeoutError as err:
            raise TileBleConnectionError(
                f"Timed out waiting for {response.name} from the Tile"
            ) from err
        finally:
            self._waiters.pop(response, None)

    async def _send_connectionless(
        self, command: ToaCommand, payload: bytes, response: ToaResponse
    ) -> ToaMessage:
        frame = build_connectionless_frame(self._token, command, payload)
        return await self._send(frame, response)

    async def request(self, message: bytes, response: ToaResponse) -> ToaMessage:
        """Send a signed message on the channel and wait for the response."""
        assert self._cid is not None
        self._nonce += 1
        frame = build_channel_frame(self._cid, self._session_key, self._nonce, message)
        return await self._send(frame, response)

    async def open(self) -> None:
        """Authenticate and open a channel."""
        authenticated = await self._send_connectionless(
            ToaCommand.AUTHENTICATE, self._rand_a, ToaResponse.AUTHENTICATE
        )
        rand_t, sres = authenticated.payload[:10], authenticated.payload[10:14]
        # Only logged: the channel handshake below is what proves the key.
        _LOGGER.debug(
            "Tile SRES %s the auth key",
            "matches"
            if sres == compute_sres(self._auth_key, self._rand_a, rand_t)
            else "does not match",
        )

        opened = await self._send_connectionless(
            ToaCommand.OPEN_CHANNEL, self._rand_a, ToaResponse.OPEN_CHANNEL
        )
        if len(opened.payload) < 1 + RAND_T_LEN:
            raise TileBleError("The Tile sent an invalid OPEN_CHANNEL response")
        cid = opened.payload[0]
        self._session_key = derive_session_key(
            self._auth_key,
            self._rand_a,
            opened.payload[1 : 1 + RAND_T_LEN],
            cid,
            self._token,
        )
        self._cid = cid
        await self.request(bytes([ToaCommand.READY, CLIENT_MPS]), ToaResponse.READY)

    async def close(self) -> None:
        """Close the channel if it is still open."""
        if self._cid is None or self._closed:
            return
        self._closed = True
        self._nonce += 1
        frame = build_channel_frame(
            self._cid,
            self._session_key,
            self._nonce,
            bytes([ToaCommand.CLOSE_CHANNEL, CloseReason.NO_ERROR]),
        )
        await self._client.write_gatt_char(TOA_CMD_CHAR_UUID, frame, response=False)


class TileBleDevice:
    """A Tile that can be reached over Bluetooth."""

    def __init__(self, ble_device: BLEDevice, auth_key: str) -> None:
        """Initialize the device with the base64 auth key from the Tile cloud."""
        self._ble_device = ble_device
        self._auth_key = decode_auth_key(auth_key)

    @asynccontextmanager
    async def _channel(self) -> AsyncIterator[_Channel]:
        try:
            client = await establish_connection(
                BleakClient,
                self._ble_device,
                self._ble_device.name or self._ble_device.address,
            )
        except (BleakError, TimeoutError) as err:
            raise TileBleConnectionError(
                f"Could not connect to the Tile: {err}"
            ) from err

        try:
            channel = _Channel(client, self._auth_key)
            try:
                await client.start_notify(
                    TOA_RSP_CHAR_UUID, channel.handle_notification
                )
                await channel.open()
                yield channel
            except BleakError as err:
                raise TileBleConnectionError(
                    f"Could not communicate with the Tile: {err}"
                ) from err
            finally:
                with suppress(BleakError):
                    await channel.close()
        finally:
            with suppress(BleakError):
                await client.disconnect()

    async def async_authenticate(self) -> None:
        """Check that the auth key belongs to this Tile."""
        async with self._channel():
            pass

    async def async_ring(self, volume: TileVolume = TileVolume.HIGH) -> None:
        """Make the Tile play its find song."""
        async with self._channel() as channel:
            response = await channel.request(
                bytes([ToaCommand.SONG, SongCommand.PLAY, TILE_SONG_FIND, volume]),
                ToaResponse.SONG,
            )
        if response.payload[:1] != bytes([SongResponse.PLAY_OK]):
            raise TileBleError(f"The Tile refused to ring: {response.payload.hex()}")
