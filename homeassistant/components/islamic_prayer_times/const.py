"""Constants for the Islamic Prayer component."""
from prayer_times_calculator import PrayerTimesCalculator

from typing import Final

DOMAIN: Final = "islamic_prayer_times"
NAME: Final = "Islamic Prayer Times"

CONF_CALC_METHOD: Final = "calculation_method"

CALC_METHODS: list[str] = list(PrayerTimesCalculator.CALCULATION_METHODS)
DEFAULT_CALC_METHOD = "isna"
