"""Module for Easy Fire sensors."""

from homeassistant.components.sensor import SensorDeviceClass

from .const import ModbusDataType, ModbusSensorEntityDescription

SENSOR_TYPES = [
    ModbusSensorEntityDescription(
        name="Outside Temperature",
        key="outside_temperature_sensor",
        register=8250,
        data_type=ModbusDataType.UINT16,
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        scale=0.1,
        status_sensor="outside_temperature_sensor_status",
    ),
    ModbusSensorEntityDescription(
        name="Outside Temperature Sensor Status",
        key="outside_temperature_sensor_status",
        register=8203,
        data_type=ModbusDataType.INT16,
        device_class=SensorDeviceClass.ENUM,
        options={0: "Faulty", 1: "Missing", 2: "OK"},
        is_status_sensor=True,
    ),
    ModbusSensorEntityDescription(
        name="Boiler Temperature",
        key="boiler_temperature",
        register=8197,
        data_type=ModbusDataType.INT16,
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        scale=0.1,
    ),
    ModbusSensorEntityDescription(
        name="Flame Temperature",
        key="flame_temperature",
        register=8215,
        data_type=ModbusDataType.INT16,
        native_unit_of_measurement="°C",
        device_class=SensorDeviceClass.TEMPERATURE,
        scale=0.1,
    ),
    ModbusSensorEntityDescription(
        name="Fuel consumption",
        key="fuel_consumption",
        register=8233,
        number_of_registries=2,
        data_type=ModbusDataType.UINT32,
        native_unit_of_measurement="kg",
        device_class=SensorDeviceClass.WEIGHT,
    ),
    ModbusSensorEntityDescription(
        name="Fill level, ash container",
        key="fill_level_ash_container",
        register=9497,
        data_type=ModbusDataType.UINT16,
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.VOLUME,
        scale=0.1,
    ),
]

SELECT_TYPES = []
