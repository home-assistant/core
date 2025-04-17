"""Constants for the Oncue integration."""

from aiokem.exceptions import CommunicationError

DOMAIN = "kem"

CONNECTION_EXCEPTIONS = (
    TimeoutError,
    CommunicationError,
)

CONNECTION_ESTABLISHED_KEY: str = "NetworkConnectionEstablished"

VALUE_UNAVAILABLE: str = "--"
