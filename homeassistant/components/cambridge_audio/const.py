"""Constants for the Cambridge Audio integration."""

import asyncio
import logging

from aiostreammagic import StreamMagicConnectionError, StreamMagicError

DOMAIN = "cambridge_audio"

LOGGER = logging.getLogger(__package__)

STREAM_MAGIC_EXCEPTIONS = (
    StreamMagicConnectionError,
    StreamMagicError,
    asyncio.CancelledError,
    TimeoutError,
)

CONNECT_TIMEOUT = 5
