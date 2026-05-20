"""Block shared access to serial ports by forcing pyserial exclusivity.

Also wires up a `serial` logger around port opens, since pyserial itself is silent.
"""

from functools import wraps
import inspect
import logging

from serial import Serial as PlatformSerial, SerialBase
from serial.rfc2217 import Serial as Rfc2217Serial
from serial.urlhandler.protocol_socket import Serial as SocketSerial

_LOGGER = logging.getLogger("pySerial")

_original_open = PlatformSerial.open
_original_socket_open = SocketSerial.open
_original_rfc2217_open = Rfc2217Serial.open


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
    """Default `exclusive` to True and log every pyserial port open."""
    if SocketSerial.open is _logged_socket_open:
        return

    defaults = {
        name: param.default
        for name, param in inspect.signature(SerialBase.__init__).parameters.items()
        if param.default is not param.empty
    }
    defaults["exclusive"] = True
    SerialBase.__init__.__defaults__ = tuple(defaults.values())

    PlatformSerial.open = _logged_platform_open  # type:ignore[method-assign]
    SocketSerial.open = _logged_socket_open  # type:ignore[method-assign]
    Rfc2217Serial.open = _logged_rfc2217_open  # type:ignore[method-assign]
