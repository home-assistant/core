"""Support for Hinen Power Sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, override

from hinen_open_api import DeviceAlertStatus, DeviceStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    ATTR_ALERT_STATUS,
    ATTR_STATUS,
    CUMULATIVE_CONSUMPTION,
    CUMULATIVE_GRID_FEED_IN,
    CUMULATIVE_PRODUCTION_ACTIVE,
    TOTAL_CHARGING_ENERGY,
    TOTAL_DISCHARGING_ENERGY,
)
from .coordinator import HinenPowerConfigEntry
from .entity import HinenDeviceEntity


@dataclass(frozen=True, kw_only=True)
class HinenSensorEntityDescription(SensorEntityDescription):
    """Describes Hinen sensor entity."""

    value_fn: Callable[[Any], StateType]


REPORTED_OPTIONS = {
    DeviceAlertStatus: [
        status.name.lower()
        for status in DeviceAlertStatus
        if status.name.lower() != "unknown"
    ],
    DeviceStatus: [
        status.name.lower()
        for status in DeviceStatus
        if status.name.lower() != "unknown"
    ],
}


def _enum_value(enum_cls: type[Enum], value: Any) -> StateType:
    """Return the lowercased enum name, unknown values return None."""
    if value is None:
        return None
    name = enum_cls(value).name.lower()
    return None if name == "unknown" else name


SENSOR_TYPES = [
    HinenSensorEntityDescription(
        key=ATTR_STATUS,
        translation_key=ATTR_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=REPORTED_OPTIONS[DeviceStatus],
        value_fn=lambda device_detail: _enum_value(
            DeviceStatus, device_detail[ATTR_STATUS]
        ),
    ),
    HinenSensorEntityDescription(
        key=ATTR_ALERT_STATUS,
        translation_key=ATTR_ALERT_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=REPORTED_OPTIONS[DeviceAlertStatus],
        value_fn=lambda device_detail: _enum_value(
            DeviceAlertStatus, device_detail[ATTR_ALERT_STATUS]
        ),
    ),
    HinenSensorEntityDescription(
        key=CUMULATIVE_CONSUMPTION,
        translation_key=CUMULATIVE_CONSUMPTION,
        value_fn=lambda device_detail: device_detail[CUMULATIVE_CONSUMPTION],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=CUMULATIVE_PRODUCTION_ACTIVE,
        translation_key=CUMULATIVE_PRODUCTION_ACTIVE,
        value_fn=lambda device_detail: device_detail[CUMULATIVE_PRODUCTION_ACTIVE],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=CUMULATIVE_GRID_FEED_IN,
        translation_key=CUMULATIVE_GRID_FEED_IN,
        value_fn=lambda device_detail: device_detail[CUMULATIVE_GRID_FEED_IN],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=TOTAL_CHARGING_ENERGY,
        translation_key=TOTAL_CHARGING_ENERGY,
        value_fn=lambda device_detail: device_detail[TOTAL_CHARGING_ENERGY],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=TOTAL_DISCHARGING_ENERGY,
        translation_key=TOTAL_DISCHARGING_ENERGY,
        value_fn=lambda device_detail: device_detail[TOTAL_DISCHARGING_ENERGY],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HinenPowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hinen sensor."""
    coordinator = entry.runtime_data.coordinator

    entities: list[HinenSensor] = [
        HinenSensor(coordinator, sensor_type, device_id)
        for device_id in coordinator.data
        for sensor_type in SENSOR_TYPES
    ]

    async_add_entities(entities)


class HinenSensor(HinenDeviceEntity, SensorEntity):
    """Representation of a Hinen sensor."""

    entity_description: HinenSensorEntityDescription

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._device_id in self.coordinator.data

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._device_id])
