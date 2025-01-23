"""Support for Roborock sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import datetime

from roborock.code_mappings import DyadError, RoborockDyadStateCode, ZeoError, ZeoState
from roborock.containers import (
    RoborockDockErrorCode,
    RoborockDockTypeCode,
    RoborockErrorCode,
    RoborockStateCode,
)
from roborock.roborock_message import (
    RoborockDataProtocol,
    RoborockDyadDataProtocol,
    RoborockZeoProtocol,
)
from roborock.roborock_typing import DeviceProp

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfArea, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator, RoborockDataUpdateCoordinatorA01
from .entity import RoborockCoordinatedEntityA01, RoborockCoordinatedEntityV1


@dataclass(frozen=True, kw_only=True)
class RoborockSensorDescription(SensorEntityDescription):
    """A class that describes Roborock sensors."""

    value_fn: Callable[[DeviceProp], StateType | datetime.datetime]

    protocol_listener: RoborockDataProtocol | None = None


@dataclass(frozen=True, kw_only=True)
class RoborockSensorDescriptionA01(SensorEntityDescription):
    """A class that describes Roborock sensors."""

    data_protocol: RoborockDyadDataProtocol | RoborockZeoProtocol


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
        key="total_cleaning_count",
        translation_key="total_cleaning_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.clean_summary.clean_count,
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
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
    ),
    RoborockSensorDescription(
        key="total_cleaning_area",
        translation_key="total_cleaning_area",
        value_fn=lambda data: data.clean_summary.square_meter_clean_area,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfArea.SQUARE_METERS,
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


A01_SENSOR_DESCRIPTIONS: list[RoborockSensorDescriptionA01] = [
    RoborockSensorDescriptionA01(
        key="status",
        data_protocol=RoborockDyadDataProtocol.STATUS,
        translation_key="a01_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=RoborockDyadStateCode.keys(),
    ),
    RoborockSensorDescriptionA01(
        key="battery",
        data_protocol=RoborockDyadDataProtocol.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    RoborockSensorDescriptionA01(
        key="filter_time_left",
        data_protocol=RoborockDyadDataProtocol.MESH_LEFT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        translation_key="filter_time_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescriptionA01(
        key="brush_remaining",
        data_protocol=RoborockDyadDataProtocol.BRUSH_LEFT,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        translation_key="brush_remaining",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescriptionA01(
        key="error",
        data_protocol=RoborockDyadDataProtocol.ERROR,
        device_class=SensorDeviceClass.ENUM,
        translation_key="a01_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=DyadError.keys(),
    ),
    RoborockSensorDescriptionA01(
        key="total_cleaning_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        data_protocol=RoborockDyadDataProtocol.TOTAL_RUN_TIME,
        device_class=SensorDeviceClass.DURATION,
        translation_key="total_cleaning_time",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescriptionA01(
        key="state",
        data_protocol=RoborockZeoProtocol.STATE,
        translation_key="zeo_state",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        options=ZeoState.keys(),
    ),
    RoborockSensorDescriptionA01(
        key="countdown",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        data_protocol=RoborockZeoProtocol.COUNTDOWN,
        device_class=SensorDeviceClass.DURATION,
        translation_key="countdown",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescriptionA01(
        key="washing_left",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        data_protocol=RoborockZeoProtocol.WASHING_LEFT,
        device_class=SensorDeviceClass.DURATION,
        translation_key="washing_left",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RoborockSensorDescriptionA01(
        key="error",
        data_protocol=RoborockZeoProtocol.ERROR,
        device_class=SensorDeviceClass.ENUM,
        translation_key="zeo_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        options=ZeoError.keys(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock vacuum sensors."""
    coordinators = config_entry.runtime_data
    async_add_entities(
        RoborockSensorEntity(
            coordinator,
            description,
        )
        for coordinator in coordinators.v1
        for description in SENSOR_DESCRIPTIONS
        if description.value_fn(coordinator.roborock_device_info.props) is not None
    )
    async_add_entities(
        RoborockSensorEntityA01(
            coordinator,
            description,
        )
        for coordinator in coordinators.a01
        for description in A01_SENSOR_DESCRIPTIONS
        if description.data_protocol in coordinator.data
    )


class RoborockSensorEntity(RoborockCoordinatedEntityV1, SensorEntity):
    """Representation of a Roborock sensor."""

    entity_description: RoborockSensorDescription

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinator,
        description: RoborockSensorDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(
            f"{description.key}_{coordinator.duid_slug}",
            coordinator,
            description.protocol_listener,
        )

    @property
    def native_value(self) -> StateType | datetime.datetime:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.roborock_device_info.props
        )


class RoborockSensorEntityA01(RoborockCoordinatedEntityA01, SensorEntity):
    """Representation of a A01 Roborock sensor."""

    entity_description: RoborockSensorDescriptionA01

    def __init__(
        self,
        coordinator: RoborockDataUpdateCoordinatorA01,
        description: RoborockSensorDescriptionA01,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = description
        super().__init__(f"{description.key}_{coordinator.duid_slug}", coordinator)

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data[self.entity_description.data_protocol]
