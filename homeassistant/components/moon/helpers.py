"""Helpers for moon phases."""

from astral import moon

from homeassistant.core import callback
from homeassistant.util import dt as dt_util

STATE_FIRST_QUARTER = "first_quarter"
STATE_FULL_MOON = "full_moon"
STATE_LAST_QUARTER = "last_quarter"
STATE_NEW_MOON = "new_moon"
STATE_WANING_CRESCENT = "waning_crescent"
STATE_WANING_GIBBOUS = "waning_gibbous"
STATE_WAXING_CRESCENT = "waxing_crescent"
STATE_WAXING_GIBBOUS = "waxing_gibbous"

# The eight moon phases in chronological order (new moon to waning crescent).
MOON_PHASES: tuple[str, ...] = (
    STATE_NEW_MOON,
    STATE_WAXING_CRESCENT,
    STATE_FIRST_QUARTER,
    STATE_WAXING_GIBBOUS,
    STATE_FULL_MOON,
    STATE_WANING_GIBBOUS,
    STATE_LAST_QUARTER,
    STATE_WANING_CRESCENT,
)


@callback
def moon_phase() -> str:
    """Return the current moon phase."""
    value: float = moon.phase(dt_util.now().date())
    if value < 0.5 or value > 27.5:
        return STATE_NEW_MOON
    if value < 6.5:
        return STATE_WAXING_CRESCENT
    if value < 7.5:
        return STATE_FIRST_QUARTER
    if value < 13.5:
        return STATE_WAXING_GIBBOUS
    if value < 14.5:
        return STATE_FULL_MOON
    if value < 20.5:
        return STATE_WANING_GIBBOUS
    if value < 21.5:
        return STATE_LAST_QUARTER
    return STATE_WANING_CRESCENT
