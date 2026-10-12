"""Support for Mikrotik routers sensors."""

from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import HEALTH, RESOURCE
from .coordinator import MikrotikConfigEntry
from .entity import MikrotikEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MikrotikSensorEntityDescription(SensorEntityDescription):
    """Shared Mikrotik Sensors entity description."""

    type: str


SENSORS: Final = (
    MikrotikSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="board-temperature1",
        translation_key="board_temperature",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="cpu-temperature",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="psu1-current",
        translation_key="psu_current",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="psu2-current",
        translation_key="psu_current",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.CURRENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="psu1-voltage",
        translation_key="psu_voltage",
        translation_placeholders={"index": "1"},
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="psu2-voltage",
        translation_key="psu_voltage",
        translation_placeholders={"index": "2"},
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="poe-out-consumption",
        translation_key="poe_out_consumption",
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        type=HEALTH,
    ),
    MikrotikSensorEntityDescription(
        key="cpu-load",
        translation_key="cpu_load",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        type=RESOURCE,
    ),
    MikrotikSensorEntityDescription(
        key="memory-usage",
        translation_key="memory_usage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        type=RESOURCE,
    ),
    MikrotikSensorEntityDescription(
        key="disk-usage",
        translation_key="disk_usage",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfRatio.PERCENTAGE,
        suggested_display_precision=2,
        type=RESOURCE,
    ),
    MikrotikSensorEntityDescription(
        key="uptime",
        device_class=SensorDeviceClass.UPTIME,
        entity_category=EntityCategory.DIAGNOSTIC,
        type=RESOURCE,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MikrotikConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mikrotik sensors based on a config entry."""

    coordinator = entry.runtime_data

    sensors_list = [
        MikrotikSensorEntity(coordinator, sensor_desc)
        for sensor_desc in SENSORS
        if coordinator.api.sensors.get(sensor_desc.type, {}).get(sensor_desc.key)
        is not None
    ]

    async_add_entities(sensors_list)


class MikrotikSensorEntity(MikrotikEntity, SensorEntity):
    """Sensor device."""

    entity_description: MikrotikSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        data = self.coordinator.api.sensors[self.entity_description.type]

        return cast(StateType | datetime, data.get(self.entity_description.key))
