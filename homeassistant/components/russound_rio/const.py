"""Constants used for Russound RIO."""

import asyncio

from aiorussound import CommandError

DOMAIN = "russound_rio"

RUSSOUND_MEDIA_TYPE_PRESET = "preset"

SELECT_SOURCE_DELAY = 0.5

RUSSOUND_RIO_EXCEPTIONS = (
    CommandError,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.CancelledError,
)
