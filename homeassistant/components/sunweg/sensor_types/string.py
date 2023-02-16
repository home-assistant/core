"""SunWEG Sensor definitions for the String type."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential

from .sensor_entity_description import SunWEGSensorEntityDescription

STRING_SENSOR_TYPES: tuple[SunWEGSensorEntityDescription, ...] = (
    SunWEGSensorEntityDescription(
        key="voltage",
        name="Voltage",
        api_key="voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        precision=2,
    ),
    SunWEGSensorEntityDescription(
        key="amperage",
        name="Amperage",
        api_key="amperage",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        precision=1,
    ),
)
