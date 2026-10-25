"""Tests for the Tile Over-the-Air protocol."""

import base64
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
import pytest
from pytest_homeassistant.components.bluetooth import generate_ble_device

from homeassistant.components.tile_ble.toa import (
    TileBleAuthenticationError,
    TileBleConnectionError,
    TileBleDevice,
    TileBleError,
    TileVolume,
    ToaMessage,
    build_channel_frame,
    build_connectionless_frame,
    compute_mic,
    decode_auth_key,
    derive_session_key,
    parse_channel_frame,
    parse_connectionless_frame,
)

from . import TILE_ADDRESS
from .fake_tile import FakeBleakClient, FakeTile

AUTH_KEY = bytes(range(16))
AUTH_KEY_B64 = base64.b64encode(AUTH_KEY).decode()
TOKEN = b"\x01\x02\x03\x04"


def test_decode_auth_key() -> None:
    """Test decoding a base64 auth key."""
    assert decode_auth_key(base64.b64encode(AUTH_KEY).decode()) == AUTH_KEY


@pytest.mark.parametrize(
    "auth_key",
    [
        pytest.param("not base64!", id="invalid_base64"),
        pytest.param(base64.b64encode(b"short").decode(), id="wrong_length"),
    ],
)
def test_decode_auth_key_invalid(auth_key: str) -> None:
    """Test invalid auth keys are rejected."""
    with pytest.raises(ValueError):
        decode_auth_key(auth_key)


def test_session_key_and_mic_are_deterministic() -> None:
    """Test the session key and MIC depend on all their inputs."""
    rand_a, rand_t = b"\xaa" * 14, b"\xbb" * 13
    session_key = derive_session_key(AUTH_KEY, rand_a, rand_t, 3, TOKEN)
    assert len(session_key) == 16
    assert session_key == derive_session_key(AUTH_KEY, rand_a, rand_t, 3, TOKEN)
    assert session_key != derive_session_key(AUTH_KEY, rand_a, rand_t, 4, TOKEN)

    mic = compute_mic(session_key, 1, b"\x12\x13")
    assert len(mic) == 4
    assert mic != compute_mic(session_key, 2, b"\x12\x13")


def test_frames() -> None:
    """Test building frames."""
    assert build_connectionless_frame(TOKEN, 0x10, b"\xaa") == (
        b"\x00" + TOKEN + b"\x10\xaa"
    )
    session_key = bytes(16)
    frame = build_channel_frame(3, session_key, 1, b"\x12\x13")
    assert frame == b"\x03\x12\x13" + compute_mic(session_key, 1, b"\x12\x13")


def test_parse_connectionless_frame() -> None:
    """Test parsing connectionless responses."""
    frame = b"\x00" + TOKEN + b"\x15\xaa\xbb"
    assert parse_connectionless_frame(frame, TOKEN) == ToaMessage(0x15, b"\xaa\xbb")
    assert parse_connectionless_frame(frame, b"\x09\x09\x09\x09") is None
    assert parse_connectionless_frame(b"\x00" + TOKEN, TOKEN) is None


def test_parse_channel_frame() -> None:
    """Test parsing channel responses strips the MIC."""
    frame = b"\x03\x07\x02" + b"\xff" * 4
    assert parse_channel_frame(frame, 3) == ToaMessage(0x07, b"\x02")
    assert parse_channel_frame(frame, 4) is None
    assert parse_channel_frame(b"\x03\x07", 3) is None


@pytest.fixture
def ble_device() -> BLEDevice:
    """Return the Tile's BLEDevice."""
    return generate_ble_device(TILE_ADDRESS, "Tile")


@contextmanager
def _connect_to(client: FakeBleakClient) -> Iterator[None]:
    with patch(
        "homeassistant.components.tile_ble.toa.establish_connection",
        AsyncMock(return_value=client),
    ):
        yield


@pytest.mark.parametrize(
    ("volume", "song"),
    [
        pytest.param(TileVolume.HIGH, b"\x02\x01\x03", id="high"),
        pytest.param(TileVolume.LOW, b"\x02\x01\x01", id="low"),
    ],
)
async def test_ring(ble_device: BLEDevice, volume: TileVolume, song: bytes) -> None:
    """Test ringing plays the find song and cleans up."""
    tile = FakeTile(AUTH_KEY)
    client = FakeBleakClient(tile)
    with _connect_to(client):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring(volume)

    assert tile.songs == [song]
    assert tile.closed_by_client
    assert client.disconnected


async def test_ignores_other_frames(ble_device: BLEDevice) -> None:
    """Test frames addressed to other clients are ignored."""
    tile = FakeTile(AUTH_KEY, send_noise=True)
    with _connect_to(FakeBleakClient(tile)):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()

    assert tile.songs == [b"\x02\x01\x03"]


async def test_authenticate(ble_device: BLEDevice) -> None:
    """Test authenticating does not ring."""
    tile = FakeTile(AUTH_KEY)
    client = FakeBleakClient(tile)
    with _connect_to(client):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_authenticate()

    assert tile.songs == []
    assert tile.closed_by_client
    assert client.disconnected


async def test_wrong_key(ble_device: BLEDevice) -> None:
    """Test a key that belongs to another Tile is rejected."""
    tile = FakeTile(bytes(16))
    client = FakeBleakClient(tile)
    with _connect_to(client), pytest.raises(TileBleAuthenticationError):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()

    assert tile.songs == []
    assert not tile.closed_by_client
    assert client.disconnected


async def test_ring_refused(ble_device: BLEDevice) -> None:
    """Test the Tile refusing to play the song."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, song_response=0x20))
    with _connect_to(client), pytest.raises(TileBleError, match="refused to ring"):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()


async def test_tile_error_response(ble_device: BLEDevice) -> None:
    """Test an error response from the Tile."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, song_error=True))
    with _connect_to(client), pytest.raises(TileBleError, match="returned an error"):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()


async def test_no_response(ble_device: BLEDevice) -> None:
    """Test a Tile that does not respond."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, respond=False))
    with (
        patch("homeassistant.components.tile_ble.toa.RESPONSE_TIMEOUT", 0.01),
        _connect_to(client),
        pytest.raises(TileBleConnectionError, match="Timed out"),
    ):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()
    assert client.disconnected


async def test_connect_fails(ble_device: BLEDevice) -> None:
    """Test the Tile cannot be connected to."""
    with (
        patch(
            "homeassistant.components.tile_ble.toa.establish_connection",
            AsyncMock(side_effect=BleakError("out of range")),
        ),
        pytest.raises(TileBleConnectionError, match="Could not connect"),
    ):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()


async def test_notify_fails(ble_device: BLEDevice) -> None:
    """Test enabling notifications failing."""
    client = FakeBleakClient(FakeTile(AUTH_KEY))
    client.start_notify = AsyncMock(side_effect=BleakError("CCCD"))  # type: ignore[method-assign]
    with (
        _connect_to(client),
        pytest.raises(TileBleConnectionError, match="Could not communicate"),
    ):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()
    assert client.disconnected


async def test_invalid_open_channel_response(ble_device: BLEDevice) -> None:
    """Test a malformed OPEN_CHANNEL response."""
    client = FakeBleakClient(FakeTile(AUTH_KEY, truncate_open_channel=True))
    with _connect_to(client), pytest.raises(TileBleError, match="invalid OPEN_CHANNEL"):
        await TileBleDevice(ble_device, AUTH_KEY_B64).async_ring()


def test_invalid_auth_key(ble_device: BLEDevice) -> None:
    """Test an invalid auth key is rejected up front."""
    with pytest.raises(ValueError):
        TileBleDevice(ble_device, "invalid")
