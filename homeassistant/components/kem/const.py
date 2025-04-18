"""Constants for the Oncue integration."""

from typing import Final

from aiokem import CommunicationError

DOMAIN = "kem"

CONNECTION_EXCEPTIONS = (
    TimeoutError,
    CommunicationError,
)

RPM: Final = "rpm"

SCAN_INTERVAL_MINUTES = 10
