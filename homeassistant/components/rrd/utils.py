"""Helper RRDTool functions."""
from datetime import timedelta

import voluptuous as vol

from .const import TIME_UNITS


def rrd_scaled_duration(duration):
    """Validate according to https://oss.oetiker.ch/rrdtool/doc/librrd.en.html#rrd_scaled_duration_(const_char_*_token,_unsigned_long_divisor,_unsigned_long_*_valuep)."""

    if isinstance(duration, int):
        # We assume duration is in seconds (RRD original behaviour)
        return duration

    scaling_factor = duration[-1]
    if scaling_factor not in ["s", "m", "h", "d", "w", "M", "y"]:
        raise vol.Invalid("Must use a scaling factor with your number")

    try:
        number = int(duration[0:-1])
        if number <= 0:
            raise vol.Invalid("Duration must be positive")
    except Exception as exc:
        raise vol.Invalid("Duration must be a number.") from exc

    return duration


def convert_to_seconds(time_str):
    """Convert time string expressed as <number>[m|h|d|s|w] to seconds."""
    # Source: https://stackoverflow.com/a/54331471

    if isinstance(time_str, int):
        # We are dealing with a raw number
        return time_str

    try:
        seconds = int(time_str)
        # We are dealing with an integer string
        return seconds
    except ValueError:
        # We are dealing with some other string or type
        pass

    # Expecting a string ending in [m|h|d|s|w]
    count = int(time_str[:-1])
    unit = TIME_UNITS[time_str[-1]]
    time_delta = timedelta(**{unit: count})
    return time_delta.seconds + 60 * 60 * 24 * time_delta.days
