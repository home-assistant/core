"""Defines the sensor types for the Module universal."""

from homeassistant.components.sensor import EntityCategory, SensorDeviceClass

from .const import ModbusDataType, ModbusSensorEntityDescription

SENSOR_TYPES = [
    ModbusSensorEntityDescription(
        name="Software Major",
        key="software_major",
        register=8192,
        data_type=ModbusDataType.UINT16,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ModbusSensorEntityDescription(
        name="Software Minor",
        key="software_minor",
        register=8193,
        data_type=ModbusDataType.UINT16,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ModbusSensorEntityDescription(
        name="Software Patch",
        key="software_patch",
        register=8194,
        data_type=ModbusDataType.UINT16,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    ModbusSensorEntityDescription(
        name="System OK",
        key="system_ok",
        register=8204,
        data_type=ModbusDataType.INT16,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options={0: "No", 1: "Yes"},
    ),
    ModbusSensorEntityDescription(
        name="Boiler fault",
        key="boiler_fault",
        register=8205,
        data_type=ModbusDataType.INT16,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options={0: "No", 1: "Yes"},
    ),
    ModbusSensorEntityDescription(
        name="Number of alarms",
        key="number_of_alarms",
        register=8252,
        data_type=ModbusDataType.INT16,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]
