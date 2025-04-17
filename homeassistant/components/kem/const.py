"""Constants for the Oncue integration."""

from typing import Final

from aiokem.exceptions import CommunicationError

DOMAIN = "kem"

CONNECTION_EXCEPTIONS = (
    TimeoutError,
    CommunicationError,
)

RPM: Final = "rpm"
