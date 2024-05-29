"""SunWEG Sensor definitions for the String type."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential

from .sensor_entity_description import SunWEGSensorEntityDescription

STRING_SENSOR_TYPES: tuple[SunWEGSensorEntityDescription, ...] = (
    SunWEGSensorEntityDescription(
        key="voltage",
        name="Voltage",
        api_variable_key="_voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        suggested_display_precision=2,
    ),
    SunWEGSensorEntityDescription(
        key="amperage",
        name="Amperage",
        api_variable_key="_amperage",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        suggested_display_precision=1,
    ),
)
