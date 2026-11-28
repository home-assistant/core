"""Sensor platform for the PiKVM integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pikvm_aio import PiKVMDeviceInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import PiKVMConfigEntry
from .entity import PiKVMEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PiKVMSensorEntityDescription(SensorEntityDescription):
    """Describes a PiKVM sensor entity."""

    value_fn: Callable[[PiKVMDeviceInfo], StateType]
    exists_fn: Callable[[PiKVMDeviceInfo], bool] = lambda _: True


SENSOR_TYPES: tuple[PiKVMSensorEntityDescription, ...] = (
    PiKVMSensorEntityDescription(
        key="cpu_temp",
        translation_key="cpu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.cpu_temp,
    ),
    PiKVMSensorEntityDescription(
        key="cpu_utilization",
        translation_key="cpu_utilization",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.cpu_utilization,
    ),
    PiKVMSensorEntityDescription(
        key="memory_utilization",
        translation_key="memory_utilization",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.memory_utilization,
    ),
    PiKVMSensorEntityDescription(
        key="fan_speed",
        translation_key="fan_speed",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.fan_speed,
        exists_fn=lambda info: info.fan_speed is not None,
    ),
    PiKVMSensorEntityDescription(
        key="msd_storage",
        translation_key="msd_storage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.msd.storage.percent_used,
        exists_fn=lambda info: info.msd.storage.percent_used is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PiKVMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PiKVM sensors based on a config entry."""
    coordinator = entry.runtime_data
    # Fan and mass storage hardware are optional; skip sensors the device lacks.
    async_add_entities(
        PiKVMSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.exists_fn(coordinator.data)
    )


class PiKVMSensor(PiKVMEntity, SensorEntity):
    """Defines a PiKVM sensor."""

    entity_description: PiKVMSensorEntityDescription

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
