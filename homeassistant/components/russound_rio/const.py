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

CONF_BAUDRATE = "baudrate"
TYPE_TCP = "tcp"
TYPE_SERIAL = "serial"
DEFAULT_BAUDRATE = 19200
DEFAULT_PORT = 9621
