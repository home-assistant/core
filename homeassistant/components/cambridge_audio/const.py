"""Constants for the Cambridge Audio integration."""

import asyncio
import logging

from aiostreammagic import StreamMagicConnectionError, StreamMagicError

from homeassistant.components.media_player import MediaType

DOMAIN = "cambridge_audio"

LOGGER = logging.getLogger(__package__)

STREAM_MAGIC_EXCEPTIONS = (
    StreamMagicConnectionError,
    StreamMagicError,
    asyncio.CancelledError,
    TimeoutError,
)

CONNECT_TIMEOUT = 5

CAMBRIDGE_MEDIA_TYPE_PRESET = "preset"
CAMBRIDGE_MEDIA_TYPE_AIRABLE = "airable"
CAMBRIDGE_MEDIA_TYPE_INTERNET_RADIO = "internet_radio"

CAMBRIDGE_RADIO = "radio"
CAMBRIDGE_TRACKS = "tracks"

CAMBRIDGE_TO_MEDIA_CLASSES = {
    CAMBRIDGE_RADIO: MediaType.CHANNEL,
    CAMBRIDGE_TRACKS: MediaType.TRACK,
}

CAMBRIDGE_TYPES_MAPPING = {
    "stream.radio": CAMBRIDGE_RADIO,
    "stream.media.local": CAMBRIDGE_TRACKS,
    "stream.service.spotify": CAMBRIDGE_TRACKS,
}
