"""Constants for the Vilfo Router integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorDeviceClass, SensorEntityDescription
from homeassistant.const import PERCENTAGE

DOMAIN = "vilfo"

ATTR_API_DATA_FIELD_LOAD = "load"
ATTR_API_DATA_FIELD_BOOT_TIME = "boot_time"
ATTR_LOAD = "load"
ATTR_BOOT_TIME = "boot_time"

ROUTER_DEFAULT_HOST = "admin.vilfo.com"
ROUTER_DEFAULT_MODEL = "Vilfo Router"
ROUTER_DEFAULT_NAME = "Vilfo Router"
ROUTER_MANUFACTURER = "Vilfo AB"


@dataclass
class VilfoRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class VilfoSensorEntityDescription(SensorEntityDescription, VilfoRequiredKeysMixin):
    """Describes Vilfo sensor entity."""


SENSOR_TYPES: tuple[VilfoSensorEntityDescription, ...] = (
    VilfoSensorEntityDescription(
        key=ATTR_LOAD,
        name="Load",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:memory",
        api_key=ATTR_API_DATA_FIELD_LOAD,
    ),
    VilfoSensorEntityDescription(
        key=ATTR_BOOT_TIME,
        name="Boot time",
        icon="mdi:timer-outline",
        api_key=ATTR_API_DATA_FIELD_BOOT_TIME,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)
