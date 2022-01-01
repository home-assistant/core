"""Support for Oncue sensors."""
from __future__ import annotations

from aiooncue import OncueDevice, OncueSensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    FREQUENCY_HERTZ,
    PERCENTAGE,
    POWER_WATT,
    PRESSURE_PSI,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

SENSORS: dict[str, SensorEntityDescription] = {
    "LatestFirmware": SensorEntityDescription(
        key="LatestFirmware",
    ),
    "EngineSpeed": SensorEntityDescription(
        key="EngineSpeed",
    ),
    "EngineOilPressure": SensorEntityDescription(
        key="EngineOilPressure",
        native_unit_of_measurement=PRESSURE_PSI,
        device_class=SensorDeviceClass.PRESSURE,
    ),
    "EngineCoolantTemperature": SensorEntityDescription(
        key="EngineCoolantTemperature", device_class=SensorDeviceClass.TEMPERATURE
    ),
    "BatteryVoltage": SensorEntityDescription(
        key="BatteryVoltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "LubeOilTemperature": SensorEntityDescription(
        key="LubeOilTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "GensetControllerTemperature": SensorEntityDescription(
        key="GensetControllerTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "EngineCompartmentTemperature": SensorEntityDescription(
        key="EngineCompartmentTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    "GeneratorTrueTotalPower": SensorEntityDescription(
        key="GeneratorTrueTotalPower",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
    ),
    "GeneratorTruePercentOfRatedPower": SensorEntityDescription(
        key="GeneratorTruePercentOfRatedPower",
        native_unit_of_measurement=PERCENTAGE,
    ),
    "GeneratorVoltageAverageLineToLine": SensorEntityDescription(
        key="GeneratorVoltageAverageLineToLine",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    "GeneratorFrequency": SensorEntityDescription(
        key="GeneratorFrequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
    ),
    "GensetState": SensorEntityDescription(
        key="GensetState",
    ),
    "GensetControllerTotalOperationTime": SensorEntityDescription(
        key="GensetControllerTotalOperationTime",
    ),
    "EngineTotalRunTime": SensorEntityDescription(
        key="EngineTotalRunTime",
    ),
    "AtsContactorPosition": SensorEntityDescription(
        key="AtsContactorPosition",
    ),
    "IPAddress": SensorEntityDescription(
        key="IPAddress",
    ),
    "ConnectedServerIPAddress": SensorEntityDescription(
        key="ConnectedServerIPAddress",
    ),
}


UNIT_MAPPINGS = {
    "C": TEMP_CELSIUS,
    "F": TEMP_FAHRENHEIT,
}


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
            OncueSensorEntity(coordinator, device_id, device, sensor, SENSORS[name])
            for name, sensor in device.sensors.items()
            if name not in SENSORS
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
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        sensors = device.sensors
        self._device_id = device_id
        self._sensor_name = sensor.name
        self._attr_unique_id = f"{device_id}_{sensor.name}"
        self._attr_name = f"{device.name} {sensor.display_name}"
        if description.native_unit_of_measurement is None and sensor.unit is not None:
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(sensor.unit)
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
        return self.coordinator.data[self._device_id].sensors[self._sensor_name].value
