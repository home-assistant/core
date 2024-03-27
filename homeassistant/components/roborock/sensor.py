"""Support for Roborock sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime

from roborock.containers import (
    RoborockDockErrorCode,
    RoborockDockTypeCode,
    RoborockErrorCode,
    RoborockStateCode,
)
from roborock.roborock_message import RoborockDataProtocol
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


@dataclass(frozen=True, kw_only=True)
class RoborockSensorDescription(SensorEntityDescription):
    """A class that describes Roborock sensors."""

    value_fn: Callable[[DeviceProp], StateType | datetime.datetime]

    protocol_listener: RoborockDataProtocol | None = None


def _dock_error_value_fn(properties: DeviceProp) -> str | None:
    if (
        status := properties.status.dock_error_status
    ) is not None and properties.status.dock_type != RoborockDockTypeCode.no_dock:
        return status.name

    return None


SENSOR_DESCRIPTIONS = [
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="main_brush_time_left",
        device_class=SensorDeviceClass.DURATION,
        translation_key="main_brush_time_left",
        value_fn=lambda data: data.consumable.main_brush_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
        protocol_listener=RoborockDataProtocol.MAIN_BRUSH_WORK_TIME,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="side_brush_time_left",
        device_class=SensorDeviceClass.DURATION,
        translation_key="side_brush_time_left",
        value_fn=lambda data: data.consumable.side_brush_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
        protocol_listener=RoborockDataProtocol.SIDE_BRUSH_WORK_TIME,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="filter_time_left",
        device_class=SensorDeviceClass.DURATION,
        translation_key="filter_time_left",
        value_fn=lambda data: data.consumable.filter_time_left,
        entity_category=EntityCategory.DIAGNOSTIC,
        protocol_listener=RoborockDataProtocol.FILTER_WORK_TIME,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="sensor_time_left",
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
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescription(
        native_unit_of_measurement=UnitOfTime.SECONDS,
        key="total_cleaning_time",
        translation_key="total_cleaning_time",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.clean_summary.clean_time,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        translation_key="status",
        value_fn=lambda data: data.status.state_name,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=RoborockStateCode.keys(),
        protocol_listener=RoborockDataProtocol.STATE,
    ),
    RoborockSensorDescription(
        key="cleaning_area",
        translation_key="cleaning_area",
        value_fn=lambda data: data.status.square_meter_clean_area,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=AREA_SQUARE_METERS,
    ),
    RoborockSensorDescription(
        key="total_cleaning_area",
        translation_key="total_cleaning_area",
        value_fn=lambda data: data.clean_summary.square_meter_clean_area,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=AREA_SQUARE_METERS,
    ),
    RoborockSensorDescription(
        key="vacuum_error",
        translation_key="vacuum_error",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda data: data.status.error_code_name,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=RoborockErrorCode.keys(),
        protocol_listener=RoborockDataProtocol.ERROR_CODE,
    ),
    RoborockSensorDescription(
        key="battery",
        value_fn=lambda data: data.status.battery,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        protocol_listener=RoborockDataProtocol.BATTERY,
    ),
    RoborockSensorDescription(
        key="last_clean_start",
        translation_key="last_clean_start",
        value_fn=lambda data: data.last_clean_record.begin_datetime
        if data.last_clean_record is not None
        else None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    RoborockSensorDescription(
        key="last_clean_end",
        translation_key="last_clean_end",
        value_fn=lambda data: data.last_clean_record.end_datetime
        if data.last_clean_record is not None
        else None,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    # Only available on some newer models
    RoborockSensorDescription(
        key="clean_percent",
        translation_key="clean_percent",
        value_fn=lambda data: data.status.clean_percent,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
    ),
    # Only available with more than just the basic dock
    RoborockSensorDescription(
        key="dock_error",
        translation_key="dock_error",
        value_fn=_dock_error_value_fn,
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=RoborockDockErrorCode.keys(),
    ),
    RoborockSensorDescription(
        key="mop_clean_remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.status.rdt,
        translation_key="mop_drying_remaining_time",
        entity_category=EntityCategory.DIAGNOSTIC,
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
        self.entity_description = description
        super().__init__(unique_id, coordinator, description.protocol_listener)

    @property
    def native_value(self) -> StateType | datetime.datetime:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.roborock_device_info.props
        )
