"""Support for Oncue sensors."""
from __future__ import annotations

from aiooncue import OncueDevice, OncueSensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
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

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="LatestFirmware",
        icon="mdi:update",
    ),
    SensorEntityDescription(key="EngineSpeed", icon="mdi:speedometer"),
    SensorEntityDescription(
        key="EngineOilPressure",
        native_unit_of_measurement=PRESSURE_PSI,
        device_class=SensorDeviceClass.PRESSURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="EngineCoolantTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="BatteryVoltage",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="LubeOilTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="GensetControllerTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="EngineCompartmentTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="GeneratorTrueTotalPower",
        native_unit_of_measurement=POWER_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="GeneratorTruePercentOfRatedPower",
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="GeneratorVoltageAverageLineToLine",
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="GeneratorFrequency",
        native_unit_of_measurement=FREQUENCY_HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(key="GensetState", icon="mdi:home-lightning-bolt"),
    SensorEntityDescription(
        key="GensetControllerTotalOperationTime", icon="mdi:hours-24"
    ),
    SensorEntityDescription(key="EngineTotalRunTime", icon="mdi:hours-24"),
    SensorEntityDescription(key="AtsContactorPosition", icon="mdi:electric-switch"),
    SensorEntityDescription(key="IPAddress", icon="mdi:ip-network"),
    SensorEntityDescription(key="ConnectedServerIPAddress", icon="mdi:server-network"),
)

SENSOR_MAP = {description.key: description for description in SENSOR_TYPES}

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
            OncueSensorEntity(coordinator, device_id, device, sensor, SENSOR_MAP[key])
            for key, sensor in device.sensors.items()
            if key in SENSOR_MAP
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
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"
        self._attr_name = f"{device.name} {sensor.display_name}"
        if not description.native_unit_of_measurement and sensor.unit is not None:
            self._attr_native_unit_of_measurement = UNIT_MAPPINGS.get(
                sensor.unit, sensor.unit
            )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            hw_version=device.hardware_version,
            sw_version=device.sensors["FirmwareVersion"].display_value,
            model=device.sensors["GensetModelNumberSelect"].display_value,
            manufacturer="Kohler",
        )

    @property
    def native_value(self) -> str | None:
        """Return the sensors state."""
        device: OncueDevice = self.coordinator.data[self._device_id]
        sensor: OncueSensor = device.sensors[self.entity_description.key]
        return sensor.value
