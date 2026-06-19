"""ESPHome serial proxy URI handler stub for serialx."""

from collections.abc import Buffer, Callable
from typing import Unpack

from serialx import BaseSerial, BaseSerialTransport, ModemPins, register_uri_handler
from serialx.common import ConnectKwargs

from homeassistant.core import Event, callback
from homeassistant.exceptions import ConfigEntryNotReady

_NOT_READY = "ESPHome has not loaded yet"


class HassESPHomeSerialStub(BaseSerial):
    """Serial stub that raises `ConfigEntryNotReady` until ESPHome itself loads."""

    def _open(self) -> None:
        """Open a connection."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _configure_port(self) -> None:
        """Configure the serial port settings."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _close(self) -> None:
        """Close the serial port."""

    @property
    def is_open(self) -> bool:
        """Return whether the serial port is open."""
        return False

    def _get_modem_pins(self) -> ModemPins:
        """Get modem control bits."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _set_modem_pins(self, modem_pins: ModemPins) -> None:
        """Set modem control bits."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _readinto(self, b: Buffer, *, timeout: float | None) -> int:
        """Read bytes from the serial port into a buffer."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _write(self, data: Buffer, *, timeout: float | None) -> int:
        """Write bytes to the serial port."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _flush(self) -> None:
        """Flush write buffers."""
        raise ConfigEntryNotReady(_NOT_READY)

    def _reset_read_buffer(self) -> None:
        """Reset the read buffer."""

    def _reset_write_buffer(self) -> None:
        """Reset the write buffer."""

    def num_unread_bytes(self) -> int:
        """Return the number of bytes waiting to be read."""
        return 0

    def num_unwritten_bytes(self) -> int:
        """Return the number of bytes waiting to be written."""
        return 0


class HassESPHomeSerialStubTransport(BaseSerialTransport):
    """Transport stub that raises `ConfigEntryNotReady` until ESPHome itself loads."""

    transport_name = "esphome-hass"

    async def _connect(
        self, *, path: str | None = None, **kwargs: Unpack[ConnectKwargs]
    ) -> None:
        """Connect to the serial port."""
        raise ConfigEntryNotReady(_NOT_READY)

    def close(self) -> None:
        """Close the transport."""
        if self._closing:
            return
        self._closing = True
        self._mark_user_closed()
        # Resolve the closed waiter so `connect()`'s failure path doesn't hang.
        self._call_protocol_connection_lost(None)

    def abort(self) -> None:
        """Abort the transport immediately."""
        self.close()

    async def _flush(self) -> None:
        """Flush write buffers."""
        raise ConfigEntryNotReady(_NOT_READY)

    async def _get_modem_pins(self) -> ModemPins:
        """Get modem control bits."""
        raise ConfigEntryNotReady(_NOT_READY)

    async def _set_modem_pins(self, modem_pins: ModemPins) -> None:
        """Set modem control bits."""
        raise ConfigEntryNotReady(_NOT_READY)


def register_serialx_transport() -> Callable[[Event], None]:
    """Register the stub URI handler."""
    unregister = register_uri_handler(
        scheme="esphome-hass://",
        unique_scheme="esphome-hass-usb://",
        sync_cls=HassESPHomeSerialStub,
        async_transport_cls=HassESPHomeSerialStubTransport,
        weight=-1,  # We want the ESPHome integration transport to take precedence
    )

    @callback
    def _unregister(event: Event) -> None:
        unregister()

    return _unregister
