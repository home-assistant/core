"""Constants for the Cambridge Audio integration."""

import asyncio
import logging

from aiostreammagic import StreamMagicConnectionError, StreamMagicError
from aiostreammagic.models import EQBand, EQFilterType

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
# Each preset contains a list of 7 EQ bands (0-6) with filter type, frequency, gain, and Q factor
# Gain range is limited to -6.0 to +3.0 dB
EQ_PRESETS: dict[str, list[EQBand]] = {
    "flat": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=0.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=0.0, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=0.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=0.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=0.0, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=0.0, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=0.0, q=0.8),
    ],
    "bass_boost": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=3.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=3.0, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=1.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=0.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=-1.0, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=-0.5, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=-0.3, q=0.8),
    ],
    "bass_reduction": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=-4.6, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=-1.8, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=-0.6, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=0.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=0.6, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=0.4, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=0.0, q=0.8),
    ],
    "voice_clarity": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=-6.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=-3.4, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=3.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=3.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=3.0, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=2.2, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=-1.4, q=0.8),
    ],
    "treble_boost": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=0.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=0.0, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=0.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=0.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=0.6, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=1.8, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=3.0, q=0.8),
    ],
    "treble_reduction": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=0.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=0.0, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=0.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=0.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=0.0, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=-1.2, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=-4.2, q=0.8),
    ],
    "tv": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=-1.9, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=-0.8, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=1.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=1.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=0.8, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=0.0, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=-0.8, q=0.8),
    ],
    "movie": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=0.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=1.4, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=-0.4, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=-2.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=-0.6, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=0.6, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=1.1, q=0.8),
    ],
    "gaming": [
        EQBand(index=0, filter=EQFilterType.LOWSHELF, freq=80, gain=3.0, q=0.8),
        EQBand(index=1, filter=EQFilterType.PEAKING, freq=120, gain=3.0, q=1.24),
        EQBand(index=2, filter=EQFilterType.PEAKING, freq=315, gain=1.0, q=1.24),
        EQBand(index=3, filter=EQFilterType.PEAKING, freq=800, gain=-1.0, q=1.24),
        EQBand(index=4, filter=EQFilterType.PEAKING, freq=2000, gain=-1.0, q=1.24),
        EQBand(index=5, filter=EQFilterType.PEAKING, freq=5000, gain=0.6, q=1.24),
        EQBand(index=6, filter=EQFilterType.HIGHSHELF, freq=8000, gain=-0.2, q=0.8),
    ],
}
