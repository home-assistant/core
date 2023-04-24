"""Support for Roborock sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    FILTER_REPLACE_TIME,
    MAIN_BRUSH_REPLACE_TIME,
    SENSOR_DIRTY_REPLACE_TIME,
    SIDE_BRUSH_REPLACE_TIME,
)
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .models import RoborockHassDeviceInfo


@dataclass
class RoborockSensorDescriptionMixin:
    """A class that describes sensor entities."""

    value_fn: Callable


@dataclass
class RoborockSensorDescription(
    SensorEntityDescription, RoborockSensorDescriptionMixin
):
    """A class that describes Roborock sensors."""


CONSUMABLE_SENSORS = [
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="main_brush_work_time",
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        translation_key="main_brush_left",
        value_fn=lambda data: MAIN_BRUSH_REPLACE_TIME
        - data.consumable.main_brush_work_time,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="side_brush_work_time",
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        translation_key="side_brush_left",
        value_fn=lambda data: SIDE_BRUSH_REPLACE_TIME
        - data.consumable.side_brush_work_time,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="filter_work_time",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.DURATION,
        translation_key="filter_left",
        value_fn=lambda data: FILTER_REPLACE_TIME - data.consumable.filter_work_time,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="sensor_dirty_time",
        icon="mdi:eye-outline",
        device_class=SensorDeviceClass.DURATION,
        translation_key="sensor_dirty_left",
        value_fn=lambda data: SENSOR_DIRTY_REPLACE_TIME
        - data.consumable.sensor_dirty_time,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum sensors."""
    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    async_add_entities(
        [
            RoborockSensorEntity(
                f"{description.key}_{slugify(device_id)}",
                device_info,
                coordinator,
                description,
            )
            for device_id, device_info in coordinator.devices_info.items()
            for description in CONSUMABLE_SENSORS
        ]
    )


class RoborockSensorEntity(RoborockCoordinatedEntity, SensorEntity):
    """Representation of a Roborock sensor."""

    entity_description: RoborockSensorDescription

    def __init__(
        self,
        unique_id: str,
        device_info: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockSensorDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(unique_id, device_info, coordinator)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self._device_id])
