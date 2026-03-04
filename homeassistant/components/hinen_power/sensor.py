"""Support for Hinen Power Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from hinen_open_api import DeviceAlertStatus, DeviceStatus, HinenOpen

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
from .coordinator import HinenDataUpdateCoordinator, HinenPowerConfigEntry
from .entity import HinenDeviceEntity


@dataclass(frozen=True, kw_only=True)
class HinenSensorEntityDescription(SensorEntityDescription):
    """Describes Hinen sensor entity."""

    available_fn: Callable[[Any], bool]
    value_fn: Callable[[Any], StateType]


SENSOR_TYPES = [
    HinenSensorEntityDescription(
        key=ATTR_STATUS,
        translation_key=ATTR_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in DeviceStatus],
        available_fn=lambda device_detail: device_detail[ATTR_STATUS] is not None,
        value_fn=lambda device_detail: DeviceStatus(
            device_detail[ATTR_STATUS]
        ).name.lower(),
    ),
    HinenSensorEntityDescription(
        key=ATTR_ALERT_STATUS,
        translation_key=ATTR_ALERT_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=[status.name.lower() for status in DeviceAlertStatus],
        available_fn=lambda device_detail: device_detail[ATTR_ALERT_STATUS] is not None,
        value_fn=lambda device_detail: DeviceAlertStatus(
            device_detail[ATTR_ALERT_STATUS]
        ).name.lower(),
    ),
    HinenSensorEntityDescription(
        key=CUMULATIVE_CONSUMPTION,
        translation_key=CUMULATIVE_CONSUMPTION,
        available_fn=lambda device_detail: (
            device_detail[CUMULATIVE_CONSUMPTION] is not None
        ),
        value_fn=lambda device_detail: device_detail[CUMULATIVE_CONSUMPTION],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=CUMULATIVE_PRODUCTION_ACTIVE,
        translation_key=CUMULATIVE_PRODUCTION_ACTIVE,
        available_fn=lambda device_detail: (
            device_detail[CUMULATIVE_PRODUCTION_ACTIVE] is not None
        ),
        value_fn=lambda device_detail: device_detail[CUMULATIVE_PRODUCTION_ACTIVE],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=CUMULATIVE_GRID_FEED_IN,
        translation_key=CUMULATIVE_GRID_FEED_IN,
        available_fn=lambda device_detail: (
            device_detail[CUMULATIVE_GRID_FEED_IN] is not None
        ),
        value_fn=lambda device_detail: device_detail[CUMULATIVE_GRID_FEED_IN],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=TOTAL_CHARGING_ENERGY,
        translation_key=TOTAL_CHARGING_ENERGY,
        available_fn=lambda device_detail: (
            device_detail[TOTAL_CHARGING_ENERGY] is not None
        ),
        value_fn=lambda device_detail: device_detail[TOTAL_CHARGING_ENERGY],
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    HinenSensorEntityDescription(
        key=TOTAL_DISCHARGING_ENERGY,
        translation_key=TOTAL_DISCHARGING_ENERGY,
        available_fn=lambda device_detail: (
            device_detail[TOTAL_DISCHARGING_ENERGY] is not None
        ),
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
    coordinator: HinenDataUpdateCoordinator = entry.runtime_data.coordinator
    hinen_open: HinenOpen = entry.runtime_data.auth.hinen_open

    entities: list = [
        HinenSensor(coordinator, hinen_open, sensor_type, device_id)
        for device_id in coordinator.data
        for sensor_type in SENSOR_TYPES
    ]

    async_add_entities(entities)


class HinenSensor(HinenDeviceEntity, SensorEntity):
    """Representation of a Hinen sensor."""

    entity_description: HinenSensorEntityDescription

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(
            self.coordinator.data[self._device_id]
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._device_id])
