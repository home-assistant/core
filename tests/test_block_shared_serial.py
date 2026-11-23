"""Tests for the block_shared_serial pyserial patches."""

from collections.abc import Generator
import logging
from unittest.mock import patch

import pytest
import serial
from serial import SerialBase, SerialException
from serial.urlhandler.protocol_socket import Serial as SocketSerial

from homeassistant import block_shared_serial


@pytest.fixture(autouse=True)
def restore_pyserial() -> Generator[None]:
    """Start from and return to unpatched pyserial state around each test."""
    block_shared_serial.disable()
    yield
    block_shared_serial.disable()


async def test_default_exclusive_becomes_true() -> None:
    """When `exclusive` is omitted, it defaults to True after enable()."""
    assert SerialBase().exclusive is None
    block_shared_serial.enable()
    assert SerialBase().exclusive is True


@pytest.mark.parametrize("value", [None, False, True])
async def test_explicit_exclusive_is_preserved(value: bool | None) -> None:
    """Explicit `exclusive` arguments are honored after enable()."""
    block_shared_serial.enable()
    assert SerialBase(exclusive=value).exclusive is value


@pytest.mark.parametrize(
    "uri",
    ["/dev/this-does-not-exist", "socket://127.0.0.1:1", "rfc2217://127.0.0.1:1"],
)
async def test_serial_open_logs(caplog: pytest.LogCaptureFixture, uri: str) -> None:
    """Opening a serial port emits a debug log on the pySerial logger."""
    block_shared_serial.enable()
    caplog.set_level(logging.DEBUG, logger="pySerial")

    # We bypass `HASocketBlockedError` checks on purpose
    with (
        pytest.raises(SerialException),
        patch("socket.socket", side_effect=RuntimeError("Cannot open socket")),
        serial.serial_for_url(uri),
    ):
        pass

    assert f"Opening serial port {uri}" in caplog.text


async def test_enable_is_idempotent() -> None:
    """Calling enable() twice leaves the existing wrappers in place."""
    block_shared_serial.enable()
    wrapped_open = SocketSerial.open
    block_shared_serial.enable()
    assert SocketSerial.open is wrapped_open


async def test_disable_restores_pyserial() -> None:
    """disable() undoes enable()."""
    original_open = SocketSerial.open
    block_shared_serial.enable()
    block_shared_serial.disable()
    assert SerialBase().exclusive is None
    assert SocketSerial.open is original_open
