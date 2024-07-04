"""Constants used for Russound RIO."""

import asyncio

from russound_rio import CommandException

DOMAIN = "russound_rio"

RUSSOUND_RIO_EXCEPTIONS = (
    CommandException,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.CancelledError,
)
