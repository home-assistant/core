"""Sensors exposing properties of the softener device."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from aioaquacell import Softener

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import AquacellConfigEntry
from .coordinator import AquacellCoordinator
from .entity import AquacellEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class SoftenerSensorEntityDescription(SensorEntityDescription):
    """Describes Softener sensor entity."""

    value_fn: Callable[[Softener], StateType]


SENSORS: tuple[SoftenerSensorEntityDescription, ...] = (
    SoftenerSensorEntityDescription(
        key="salt_left_side_percentage",
        translation_key="salt_left_side_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda softener: softener.salt.leftPercent,
    ),
    SoftenerSensorEntityDescription(
        key="salt_right_side_percentage",
        translation_key="salt_right_side_percentage",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda softener: softener.salt.rightPercent,
    ),
    SoftenerSensorEntityDescription(
        key="salt_left_side_remaining_days",
        translation_key="salt_left_side_remaining_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda softener: softener.salt.leftDays,
    ),
    SoftenerSensorEntityDescription(
        key="salt_right_side_remaining_days",
        translation_key="salt_right_side_remaining_days",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda softener: softener.salt.rightDays,
    ),
    SoftenerSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda softener: softener.battery,
    ),
    SoftenerSensorEntityDescription(
        key="wifi_level",
        translation_key="wifi_level",
        value_fn=lambda softener: softener.wifiLevel,
        device_class=SensorDeviceClass.ENUM,
        options=[
            "high",
            "medium",
            "low",
        ],
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AquacellConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensors."""
    for idx, _ in enumerate(config_entry.runtime_data.data):
        async_add_entities(
            SoftenerSensor(config_entry.runtime_data, sensor, idx) for sensor in SENSORS
        )


class SoftenerSensor(AquacellEntity, SensorEntity):
    """Softener sensor."""

    entity_description: SoftenerSensorEntityDescription
    _softener_index: int

    def __init__(
        self,
        coordinator: AquacellCoordinator,
        description: SoftenerSensorEntityDescription,
        softener_index: int,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator, coordinator.data[softener_index], description)

        self.entity_description = description
        self._softener_index = softener_index

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.softener)

    @property
    def softener(self) -> Softener:
        """Handle updated data from the coordinator."""
        return self.coordinator.data[self._softener_index]
