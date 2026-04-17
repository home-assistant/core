"""Constants for the Honeywell String Lights integration."""

from __future__ import annotations

from typing import Final

from rf_protocols import Timing

DOMAIN: Final = "honeywell_string_lights"

CONF_TRANSMITTER: Final = "transmitter"

FREQUENCY: Final = 433_920_000
REPEAT_COUNT: Final = 50


def _parse_timings(raw: list[int]) -> list[Timing]:
    """Convert raw alternating high/low microsecond values to Timing objects."""
    return [
        Timing(high_us=high, low_us=-low)
        for high, low in zip(raw[::2], raw[1::2], strict=True)
    ]


TURN_ON_TIMINGS: Final = _parse_timings(
    [
        2000,
        -550,
        1000,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
    ]
)

TURN_OFF_TIMINGS: Final = _parse_timings(
    [
        2000,
        -550,
        1000,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        1000,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        450,
        -550,
        1000,
        -550,
    ]
)
