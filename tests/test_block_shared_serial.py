"""Tests for the block_shared_serial pyserial monkey-patches."""

from collections.abc import Generator
import logging
from unittest.mock import patch

import pytest
import serial
from serial import Serial as PlatformSerial, SerialBase, SerialException
from serial.rfc2217 import Serial as Rfc2217Serial
from serial.urlhandler.protocol_socket import Serial as SocketSerial

from homeassistant import block_shared_serial


@pytest.fixture(autouse=True)
def restore_pyserial() -> Generator[None]:
    """Restore the patched pyserial methods after each test."""
    try:
        yield
    finally:
        SerialBase.__init__ = block_shared_serial._original_init
        PlatformSerial.open = block_shared_serial._original_open
        SocketSerial.open = block_shared_serial._original_socket_open
        Rfc2217Serial.open = block_shared_serial._original_rfc2217_open


@pytest.mark.parametrize("requested", [None, False, True])
async def test_init_forces_exclusive(requested: bool | None) -> None:
    """Test that __init__ always coerces exclusive to True after enable()."""
    base1 = SerialBase(exclusive=requested)
    assert base1.exclusive is requested

    block_shared_serial.enable()
    base2 = SerialBase(exclusive=requested)
    assert base2.exclusive is True


@pytest.mark.parametrize(
    "uri",
    [
        "/dev/this-does-not-exist",
        "socket://127.0.0.1:1",
        "rfc2217://127.0.0.1:1",
    ],
)
async def test_serial_open_logs(caplog: pytest.LogCaptureFixture, uri: str) -> None:
    """Test that opening a serial port emits a debug log on the serial logger."""
    block_shared_serial.enable()
    caplog.set_level(logging.DEBUG, logger="serial")

    with (  # noqa: SIM117
        pytest.raises(SerialException),
        # We bypass `HASocketBlockedError` checks on purpose
        patch("socket.socket", side_effect=RuntimeError("Cannot open socket")),
    ):
        with serial.serial_for_url(uri):
            pass

    assert f"Opening serial port {uri}" in caplog.text


async def test_enable_multiple_times() -> None:
    """Test that calling enable() twice raises RuntimeError."""
    block_shared_serial.enable()

    with pytest.raises(RuntimeError, match="Shared serial blocking is already enabled"):
        block_shared_serial.enable()
