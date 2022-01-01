"""Support for Oncue sensors."""
from __future__ import annotations

from aiooncue import OncueDevice, OncueSensor

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS, TEMP_FAHRENHEIT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

STATIC_SENSORS = {
    "GensetSerialNumber",
    "GensetModelNumberSelect",
    "FirmwareVersion",
    "Product",
}

DEVICE_CLASSES = {
    "EngineOilPressure": SensorDeviceClass.PRESSURE,  # its PSI though
    "EngineCoolantTemperature": SensorDeviceClass.TEMPERATURE,
    "BatteryVoltage": SensorDeviceClass.VOLTAGE,
    "LubeOilTemperature": SensorDeviceClass.TEMPERATURE,
    "GensetControllerTemperature": SensorDeviceClass.TEMPERATURE,
    "EngineCompartmentTemperature": SensorDeviceClass.TEMPERATURE,
    "GeneratorTrueTotalPower": SensorDeviceClass.POWER,
    "GeneratorVoltageAverageLineToLine": SensorDeviceClass.VOLTAGE,
    "GeneratorFrequency": SensorDeviceClass.FREQUENCY,
}
UNIT_MAPPINGS = {"C": TEMP_CELSIUS, "F": TEMP_FAHRENHEIT}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[OncueSensorEntity] = []
    devices: dict[str, OncueDevice] = coordinator.data
    for device_id, device in devices.items():
        entities.extend(
            OncueSensorEntity(
                coordinator,
                device_id,
                device,
                sensor,
            )
            for name, sensor in device.sensors.items()
            if name not in STATIC_SENSORS
        )

    async_add_entities(entities)


class OncueSensorEntity(CoordinatorEntity, SensorEntity):
    """Representation of an Oncue sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device_id: str,
        device: OncueDevice,
        sensor: OncueSensor,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        sensors = device.sensors
        self._device_id = device_id
        self._sensor_name = sensor.name
        self._attr_unique_id = f"{device_id}_{sensor.name}"
        self._attr_name = f"{device.name} {sensor.display_name}"
        self._attr_device_class = DEVICE_CLASSES.get(sensor.name)
        if sensor.unit is not None:
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(
                sensor.unit, sensor.unit
            )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            hw_version=device.hardware_version,
            sw_version=sensors["FirmwareVersion"].display_value,
            model=sensors["GensetModelNumberSelect"].display_value,
            manufacturer="Kohler",
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensors state."""
        return self.coordinator.data[self._device_id].sensors[self._sensor_name][
            "value"
        ]
