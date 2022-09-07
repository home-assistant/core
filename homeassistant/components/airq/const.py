"""Constants for the air-Q integration."""
from typing import Final

from homeassistant.backports.enum import StrEnum

DOMAIN: Final = "airq"
MANUFACTURER: Final = "CorantGmbH"
TARGET_ROUTE: Final = "average"
CONCENTRATION_GRAMS_PER_CUBIC_METER: Final = "g/m³"


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
