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
    except Exception:
        raise vol.Invalid("Duration must be a number.")

    return duration


def convert_to_seconds(s):
    """Convert time string expressed as <number>[m|h|d|s|w] to seconds."""
    # Source: https://stackoverflow.com/a/54331471

    if isinstance(s, int):
        # We are dealing with a raw number
        return s

    try:
        seconds = int(s)
        # We are dealing with an integer string
        return seconds
    except ValueError:
        # We are dealing with some other string or type
        pass

    # Expecting a string ending in [m|h|d|s|w]
    count = int(s[:-1])
    unit = TIME_UNITS[s[-1]]
    td = timedelta(**{unit: count})
    return td.seconds + 60 * 60 * 24 * td.days
