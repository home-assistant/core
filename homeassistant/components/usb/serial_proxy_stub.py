"""ESPHome serial proxy URI handler stub for serialx."""

from __future__ import annotations

from collections.abc import Callable

from serialx import register_uri_handler
from serialx.platforms.serial_esphome import ESPHomeSerial, ESPHomeSerialTransport

from homeassistant.core import Event, callback
from homeassistant.exceptions import ConfigEntryNotReady


class HassESPHomeSerialStub(ESPHomeSerial):
    """ESPHomeSerial that throws `ConfigEntryNotReady` until ESPHome itself loads."""

    async def _async_open(self) -> None:
        """Open a connection."""
        raise ConfigEntryNotReady("ESPHome has not loaded yet")


class HassESPHomeSerialStubTransport(ESPHomeSerialTransport):
    """Transport variant that constructs `HassESPHomeSerialStub`."""

    transport_name = "esphome-hass"
    _serial_cls = HassESPHomeSerialStub


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
