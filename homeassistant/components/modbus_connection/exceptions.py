"""Exceptions for the Modbus Connection integration."""

from modbus_connection import ModbusError

from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN


class ConnectionNotReady(ConfigEntryNotReady, ModbusError):
    """The shared Modbus connection is missing or not loaded.

    Raised by ``async_get_unit``. It is a ``ConfigEntryNotReady`` so a consumer
    integration can let it propagate from its own ``async_setup_entry`` to get
    Home Assistant's setup-retry behaviour, and a ``ModbusError`` so it is also
    catchable with the library's error type.
    """

    def __init__(self, connection_entry_id: str) -> None:
        """Initialize the error."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="connection_not_ready",
        )
        self.connection_entry_id = connection_entry_id
