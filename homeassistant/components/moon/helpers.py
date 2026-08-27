"""Helpers for moon phases."""

import math
from typing import Any

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

# Phase calculation returns 0-27.99; illumination increases up to the full moon
# (value 14) and decreases afterwards.
_FULL_MOON_PHASE_VALUE = 14


class _Moon:
    """Moon calculation helper."""

    @staticmethod
    def phase(
        target_date: Any = None,
    ) -> float:
        """Calculate the phase of the moon (0..27.99) for a given date/datetime."""
        if target_date is None:
            target_date = dt_util.utcnow()

        if hasattr(target_date, "hour"):
            target_date = dt_util.as_utc(target_date)
            day_fraction = (
                target_date.hour * 3600
                + target_date.minute * 60
                + target_date.second
                + target_date.microsecond / 1_000_000
            ) / 86400.0
        else:
            day_fraction = 0.0

        year = target_date.year
        month = target_date.month
        day = target_date.day

        if month <= 2:
            year -= 1
            month += 12

        century = year // 100
        greg_corr = 2 - century + (century // 4)
        julian_day = (
            int(365.25 * (year + 4716))
            + int(30.6001 * (month + 1))
            + day
            + day_fraction
            + greg_corr
            - 1524.5
        )

        delta_t = pow((julian_day - 2382148), 2) / (41048480 * 86400)
        centuries = (julian_day + delta_t - 2451545.0) / 36525
        cent_sq = pow(centuries, 2)
        cent_cube = pow(centuries, 3)

        mean_elong = math.radians(
            (
                297.85
                + 445267.1115 * centuries
                - 0.0016300 * cent_sq
                + cent_cube / 545868
            )
            % 360.0
        )
        sun_anomaly = math.radians((357.53 + 35999.0503 * centuries) % 360.0)
        moon_anomaly = math.radians(
            (134.96 + 477198.8676 * centuries + 0.0089970 * cent_sq + cent_cube / 69699)
            % 360.0
        )

        elongation = math.degrees(mean_elong) + 6.29 * math.sin(moon_anomaly)
        elongation -= 2.10 * math.sin(sun_anomaly)
        elongation += 1.27 * math.sin(2 * mean_elong - moon_anomaly)
        elongation += 0.66 * math.sin(2 * mean_elong)
        elong_deg = int(elongation % 360.0)

        phase_val = ((elong_deg + 6.43) / 360.0) * 28.0
        if phase_val >= 28.0:
            phase_val -= 28.0
        return phase_val


moon = _Moon()


@callback
def moon_phase() -> str:
    """Return the current moon phase."""
    value: float = moon.phase(dt_util.now())
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
def is_waxing() -> bool:
    """Return whether the moon is currently waxing (illumination increasing)."""
    value: float = moon.phase(dt_util.now())
    return value < _FULL_MOON_PHASE_VALUE
