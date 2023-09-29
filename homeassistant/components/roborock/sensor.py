"""Support for Roborock sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from roborock.containers import RoborockErrorCode, RoborockStateCode
from roborock.roborock_typing import DeviceProp

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    AREA_SQUARE_METERS,
    PERCENTAGE,
    EntityCategory,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


@dataclass
class RoborockSensorDescriptionMixin:
    """A class that describes sensor entities."""

    value_fn: Callable[[DeviceProp], int]


@dataclass
class RoborockSensorDescription(
    SensorEntityDescription, RoborockSensorDescriptionMixin
):
    """A class that describes Roborock sensors."""


SENSOR_DESCRIPTIONS = [
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="main_brush_time_left",
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        translation_key="main_brush_time_left",
        value_fn=lambda data: data.consumable.main_brush_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="side_brush_time_left",
        icon="mdi:brush",
        device_class=SensorDeviceClass.DURATION,
        translation_key="side_brush_time_left",
        value_fn=lambda data: data.consumable.side_brush_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="filter_time_left",
        icon="mdi:air-filter",
        device_class=SensorDeviceClass.DURATION,
        translation_key="filter_time_left",
        value_fn=lambda data: data.consumable.filter_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="sensor_time_left",
        icon="mdi:eye-outline",
        device_class=SensorDeviceClass.DURATION,
        translation_key="sensor_time_left",
        value_fn=lambda data: data.consumable.sensor_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="cleaning_time",
        translation_key="cleaning_time",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.status.clean_time,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="total_cleaning_time",
        translation_key="total_cleaning_time",
        icon="mdi:history",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.clean_summary.clean_time,
    ),
    RoborockSensorDescription(
        key="status",
        icon="mdi:information-outline",
        device_class=SensorDeviceClass.ENUM,
        translation_key="status",
        value_fn=lambda data: data.status.state.name,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=RoborockStateCode.keys(),
    ),
    RoborockSensorDescription(
        key="cleaning_area",
        icon="mdi:texture-box",
        translation_key="cleaning_area",
        value_fn=lambda data: data.status.square_meter_clean_area,
        native_unit_of_measurement=AREA_SQUARE_METERS,
    ),
    RoborockSensorDescription(
        key="total_cleaning_area",
        icon="mdi:texture-box",
        translation_key="total_cleaning_area",
        value_fn=lambda data: data.clean_summary.square_meter_clean_area,
        native_unit_of_measurement=AREA_SQUARE_METERS,
    ),
    RoborockSensorDescription(
        key="vacuum_error",
        icon="mdi:alert-circle",
        translation_key="vacuum_error",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: data.status.error_code.name,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=RoborockErrorCode.keys(),
    ),
    RoborockSensorDescription(
        key="battery",
        value_fn=lambda data: data.status.battery,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum sensors."""
    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockSensorEntity(
            f"{description.key}_{slugify(device_id)}",
            coordinator,
            description,
        )
        for device_id, coordinator in coordinators.items()
        for description in SENSOR_DESCRIPTIONS
        if description.value_fn(coordinator.roborock_device_info.props) is not None
    )


class RoborockSensorEntity(RoborockCoordinatedEntity, SensorEntity):
    """Representation of a Roborock sensor."""

    entity_description: RoborockSensorDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockSensorDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(unique_id, coordinator)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.roborock_device_info.props
        )
