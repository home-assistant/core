"""Defines models used by the integration."""
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_TEMPERATURE,
    UnitOfElectricPotential,
    UnitOfTemperature,
)


class SensorTypes:
    """Collection of sensor entities defining measurements of a device."""

    class SensorType:
        """Base entity type."""

        DATA_KEY: str
        UNIT: str
        DEVICE_CLASS: SensorDeviceClass
        NAME: str

    class BatteryLevel(SensorType):
        """Battery entity type."""

        DATA_KEY = ATTR_BATTERY_LEVEL
        UNIT = UnitOfElectricPotential.VOLT
        DEVICE_CLASS = SensorDeviceClass.VOLTAGE
        NAME = "Battery level"

    class Temperature(SensorType):
        """Temperature entity type."""

        DATA_KEY = ATTR_TEMPERATURE
        UNIT = UnitOfTemperature.CELSIUS
        DEVICE_CLASS = SensorDeviceClass.TEMPERATURE
        NAME = "Temperature"
