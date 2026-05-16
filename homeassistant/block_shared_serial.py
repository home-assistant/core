"""Block shared access to serial ports by forcing pyserial exclusivvity.

Also wires up a `serial` logger around port opens, since pyserial itself is silent.
"""

from functools import wraps
import logging
from typing import Any

from serial import Serial as PlatformSerial, SerialBase
from serial.rfc2217 import Serial as Rfc2217Serial
from serial.urlhandler.protocol_socket import Serial as SocketSerial

_LOGGER = logging.getLogger("pySerial")

_original_init = SerialBase.__init__
_original_open = PlatformSerial.open
_original_socket_open = SocketSerial.open
_original_rfc2217_open = Rfc2217Serial.open


@wraps(_original_init)
def _exclusive_init(self: SerialBase, *args: Any, **kwargs: Any) -> None:
    kwargs["exclusive"] = True
    _original_init(self, *args, **kwargs)


@wraps(_original_open)
def _logged_platform_open(self: PlatformSerial) -> None:
    _LOGGER.debug("Opening serial port %s", self.port)
    _original_open(self)
    _LOGGER.debug("Opened serial port %s", self.port)


@wraps(_original_socket_open)
def _logged_socket_open(self: SocketSerial) -> None:
    _LOGGER.debug("Opening serial port %s", self.port)
    _original_socket_open(self)
    _LOGGER.debug("Opened serial port %s", self.port)


@wraps(_original_rfc2217_open)
def _logged_rfc2217_open(self: Rfc2217Serial) -> None:
    _LOGGER.debug("Opening serial port %s", self.port)
    _original_rfc2217_open(self)
    _LOGGER.debug("Opened serial port %s", self.port)


def enable() -> None:
    """Force exclusive locking and log every pyserial port open."""
    if SerialBase.__init__ is _exclusive_init:
        raise RuntimeError("Shared serial blocking is already enabled")

    SerialBase.__init__ = _exclusive_init  # type:ignore[method-assign]
    PlatformSerial.open = _logged_platform_open  # type:ignore[method-assign]
    SocketSerial.open = _logged_socket_open  # type:ignore[method-assign]
    Rfc2217Serial.open = _logged_rfc2217_open  # type:ignore[method-assign]
