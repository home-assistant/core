"""Constants for the air-Q integration."""
from typing import Final

from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "airq"
MANUFACTURER: Final = "CorantGmbH"
TARGET_ROUTE: Final = "average"
CONCENTRATION_GRAMS_PER_CUBIC_METER: Final = "g/m³"
COUNT_PER_DECILITERS: Final = "1/dL"
LENGTH_MICROMETERS: Final = "μm"


class SensorDeviceClass(StrEnum):
    """Additional device classes for sensors in air-Q.

    This class extends homeassistant.components.sensor.SensorDeviceClass
    """

    DEWPOINT = "dew_point"  # (°C)
    H2S = "hydrogen_sulfide"  # (µg/m³)

    # Besides the relative humidity in %, air-Q provides
    HUMIDITY_ABS = "absolute_humidity"  # (g/m³)

    # Calculated proprietary indices (integer between 0 and 1000):
    INDEX_HEALTH = "heath_index"  # Alarms: gas = -200; fire = -800
    INDEX_PERFORMANCE = "performance_index"

    OXYGEN = "oxygen"  # (volume %)
    SOUND = "sound"  # (dB(A))

    # Total count of particulates with size > X µm in 100 ml:
    # E.g. cnt2_5 = cnt10 + cnt5
    CNT0_3 = "cnt0.3"
    CNT0_5 = "cnt0.5"
    CNT1 = "cnt1"
    CNT2_5 = "cnt2.5"
    CNT5 = "cnt5"
    CNT10 = "cnt10"

    MEAN_PM_SIZE = "mean_particulates_size"  # (µm)
