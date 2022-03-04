"""Constants for the Airzone integration."""

from typing import Final

from aioairzone.const import AZD_HUMIDITY, AZD_TEMP

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    ENTITY_CATEGORY_DIAGNOSTIC,
    PERCENTAGE,
    TEMP_CELSIUS,
)

DOMAIN = "airzone"
MANUFACTURER = "Airzone"

AIOAIRZONE_DEVICE_TIMEOUT_SEC: Final = 10
DEFAULT_LOCAL_API_HOST: Final = ""
DEFAULT_LOCAL_API_PORT: Final = 3000

SENSOR_TYPES: Final[tuple[SensorEntityDescription, ...]] = (
    SensorEntityDescription(
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=AZD_TEMP,
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    SensorEntityDescription(
        device_class=DEVICE_CLASS_HUMIDITY,
        entity_category=ENTITY_CATEGORY_DIAGNOSTIC,
        key=AZD_HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
)
