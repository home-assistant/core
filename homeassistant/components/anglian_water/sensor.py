"""Anglian Water sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pyanglianwater.meter import SmartMeter

from homeassistant.components.sensor import (
    EntityCategory,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AnglianWaterConfigEntry, AnglianWaterUpdateCoordinator
from .entity import AnglianWaterEntity

PARALLEL_UPDATES = 0


class AnglianWaterSensor(StrEnum):
    """Store keys for Anglian Water sensors."""

    YESTERDAY_CONSUMPTION = "yesterday_consumption"
    YESTERDAY_WATER_COST = "yesterday_water_cost"
    YESTERDAY_SEWERAGE_COST = "yesterday_sewerage_cost"
    LATEST_READING = "latest_reading"


@dataclass(frozen=True, kw_only=True)
class AnglianWaterSensorEntityDescription(SensorEntityDescription):
    """Describes AnglianWater sensor entity."""

    value_fn: Callable[[SmartMeter], float]


ENTITY_DESCRIPTIONS: tuple[AnglianWaterSensorEntityDescription, ...] = (
    AnglianWaterSensorEntityDescription(
        key=AnglianWaterSensor.YESTERDAY_CONSUMPTION,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda entity: entity.get_yesterday_consumption,
        state_class=SensorStateClass.TOTAL,
        translation_key=AnglianWaterSensor.YESTERDAY_CONSUMPTION,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AnglianWaterSensorEntityDescription(
        key=AnglianWaterSensor.LATEST_READING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        device_class=SensorDeviceClass.WATER,
        value_fn=lambda entity: entity.latest_read,
        state_class=SensorStateClass.TOTAL_INCREASING,
        translation_key=AnglianWaterSensor.LATEST_READING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AnglianWaterSensorEntityDescription(
        key=AnglianWaterSensor.YESTERDAY_WATER_COST,
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda entity: entity.yesterday_water_cost,
        translation_key=AnglianWaterSensor.YESTERDAY_WATER_COST,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AnglianWaterSensorEntityDescription(
        key=AnglianWaterSensor.YESTERDAY_SEWERAGE_COST,
        native_unit_of_measurement="GBP",
        device_class=SensorDeviceClass.MONETARY,
        value_fn=lambda entity: entity.yesterday_sewerage_cost,
        translation_key=AnglianWaterSensor.YESTERDAY_SEWERAGE_COST,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnglianWaterConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    async_add_devices(
        AnglianWaterSensorEntity(
            coordinator=entry.runtime_data,
            description=entity_description,
            smart_meter=smart_meter,
        )
        for entity_description in ENTITY_DESCRIPTIONS
        for smart_meter in entry.runtime_data.api.meters.values()
    )


class AnglianWaterSensorEntity(AnglianWaterEntity, SensorEntity):
    """Defines a Anglian Water sensor."""

    entity_description: AnglianWaterSensorEntityDescription

    def __init__(
        self,
        coordinator: AnglianWaterUpdateCoordinator,
        smart_meter: SmartMeter,
        description: AnglianWaterSensorEntityDescription,
    ) -> None:
        """Initialize Anglian Water sensor."""
        super().__init__(coordinator, smart_meter, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.smart_meter)
