"""Constants for the Islamic Prayer component."""
from prayer_times_calculator import PrayerTimesCalculator
from homeassistant.components.sensor import SensorEntityDescription

DOMAIN = "islamic_prayer_times"
NAME = "Islamic Prayer Times"
PRAYER_TIMES_ICON = "mdi:calendar-clock"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="Fajr",
        name="Fajr prayer",
    ),
    SensorEntityDescription(
        key="Sunrise",
        name="Sunrise time",
    ),
    SensorEntityDescription(
        key="Dhuhr",
        name="Dhuhr prayer",
    ),
    SensorEntityDescription(
        key="Asr",
        name="Asr prayer",
    ),
    SensorEntityDescription(
        key="Maghrib",
        name="Maghrib prayer",
    ),
    SensorEntityDescription(
        key="Isha",
        name="Isha prayer",
    ),
    SensorEntityDescription(
        key="Midnight",
        name="Midnight time",
    ),
)

CONF_CALC_METHOD = "calculation_method"

CALC_METHODS: list[str] = list(PrayerTimesCalculator.CALCULATION_METHODS)
DEFAULT_CALC_METHOD = "isna"
