"""Helpers for moon phases."""

from typing import NamedTuple, cast

from skyfield import almanac
from skyfield.api import Loader
from skyfield.jpllib import SpiceKernel
from skyfield.timelib import Timescale

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from .const import DOMAIN

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

# Scale Skyfield's phase angle to the 28-day scale used by the phase thresholds.
_LUNAR_CYCLE_DAYS = 28
_FULL_MOON_PHASE_VALUE = 14


class MoonData(NamedTuple):
    """The ephemeris and timescale used for moon calculations."""

    ephemeris: SpiceKernel
    timescale: Timescale


type MoonConfigEntry = ConfigEntry[MoonData]


def load_moon_data(directory: str) -> MoonData:
    """Load the 17 MB planetary ephemeris and built-in timescale."""
    loader = Loader(directory)
    return MoonData(loader("de421.bsp"), loader.timescale(builtin=True))


@callback
def get_moon_data(hass: HomeAssistant) -> MoonData:
    """Return the loaded Moon config entry data."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    return cast(MoonConfigEntry, entry).runtime_data


@callback
def _phase_value(moon_data: MoonData) -> float:
    """Return the current moon phase on a 28-day scale."""
    now = dt_util.utcnow()
    time = moon_data.timescale.from_datetime(now)
    phase_angle = almanac.moon_phase(moon_data.ephemeris, time).degrees
    return float(phase_angle * (_LUNAR_CYCLE_DAYS / 360))


@callback
def moon_phase(moon_data: MoonData) -> str:
    """Return the current moon phase."""
    value = _phase_value(moon_data)
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


@callback
def is_waxing(moon_data: MoonData) -> bool:
    """Return whether the moon is currently waxing (illumination increasing)."""
    value = _phase_value(moon_data)
    return value < _FULL_MOON_PHASE_VALUE
