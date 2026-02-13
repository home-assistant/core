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

CAMBRIDGE_MEDIA_TYPE_PRESET = "preset"
CAMBRIDGE_MEDIA_TYPE_AIRABLE = "airable"
CAMBRIDGE_MEDIA_TYPE_INTERNET_RADIO = "internet_radio"

# EQ preset key for identifying when custom EQ is in use
EQ_PRESET_CUSTOM = "custom"

# EQ preset definitions from the official StreamMagic app
# Each preset contains 7 gain values (dB) for bands 0-6
# Gain range is limited to -6.0 to +3.0 dB
EQ_PRESET_GAINS: dict[str, list[float]] = {
    "flat": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
    "bass_boost": [3.0, 3.0, 1.0, 0.0, -1.0, -0.5, -0.3],
    "bass_reduction": [-4.6, -1.8, -0.6, 0.0, 0.6, 0.4, 0.0],
    "voice_clarity": [-6.0, -3.4, 3.0, 3.0, 3.0, 2.2, -1.4],
    "treble_boost": [0.0, 0.0, 0.0, 0.0, 0.6, 1.8, 3.0],
    "treble_reduction": [0.0, 0.0, 0.0, 0.0, 0.0, -1.2, -4.2],
    "tv": [-1.9, -0.8, 1.0, 1.0, 0.8, 0.0, -0.8],
    "movie": [0.0, 1.4, -0.4, -2.0, -0.6, 0.6, 1.1],
    "gaming": [3.0, 3.0, 1.0, -1.0, -1.0, 0.6, -0.2],
}
