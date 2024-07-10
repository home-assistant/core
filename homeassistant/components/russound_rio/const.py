"""Constants used for Russound RIO."""

import asyncio

from aiorussound import CommandException

DOMAIN = "russound_rio"

RUSSOUND_RIO_EXCEPTIONS = (
    CommandException,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.CancelledError,
)


class NoPrimaryControllerException(Exception):
    """Thrown when the Russound device is not the primary unit in the RNET stack."""


CONNECT_TIMEOUT = 5
