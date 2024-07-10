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
