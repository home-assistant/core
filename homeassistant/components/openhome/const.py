"""Constants for the Openhome component."""

from enum import StrEnum

DOMAIN = "openhome"

DATA_OPENHOME = "openhome"


class OpenhomeService(StrEnum):
    """Store keys for Openhome services."""

    INVOKE_PIN = "invoke_pin"


class OpenhomeServiceArgument(StrEnum):
    """Store keys for Openhome service arguments."""

    PIN = "pin"
