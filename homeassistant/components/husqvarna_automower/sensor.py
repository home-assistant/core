"""Creates a the sensor entities for the mower."""
from collections.abc import Callable
from dataclasses import dataclass
import datetime
import logging

from aioautomower.model import MowerAttributes, MowerModes

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AutomowerSensorEntityDescription(SensorEntityDescription):
    """Describes Automower sensor entity."""

    exists_fn: Callable[[MowerAttributes], bool] = lambda _: True
    value_fn: Callable[[MowerAttributes], str]


SENSOR_TYPES: tuple[AutomowerSensorEntityDescription, ...] = (
    AutomowerSensorEntityDescription(
        key="battery_percent",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.battery.battery_percent,
    ),
    AutomowerSensorEntityDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=[option.lower() for option in list(MowerModes)],
        value_fn=(
            lambda data: data.mower.mode.lower()
            if data.mower.mode != MowerModes.UNKNOWN
            else None
        ),
    ),
    AutomowerSensorEntityDescription(
        key="cutting_blade_usage_time",
        translation_key="cutting_blade_usage_time",
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        exists_fn=lambda data: data.statistics.cutting_blade_usage_time is not None,
        value_fn=lambda data: data.statistics.cutting_blade_usage_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_charging_time",
        translation_key="total_charging_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.statistics.total_charging_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_cutting_time",
        translation_key="total_cutting_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.statistics.total_cutting_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_running_time",
        translation_key="total_running_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.statistics.total_running_time,
    ),
    AutomowerSensorEntityDescription(
        key="total_searching_time",
        translation_key="total_searching_time",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: data.statistics.total_searching_time,
    ),
    AutomowerSensorEntityDescription(
        key="number_of_charging_cycles",
        translation_key="number_of_charging_cycles",
        icon="mdi:battery-sync-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.statistics.number_of_charging_cycles,
    ),
    AutomowerSensorEntityDescription(
        key="number_of_collisions",
        translation_key="number_of_collisions",
        icon="mdi:counter",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: data.statistics.number_of_collisions,
    ),
    AutomowerSensorEntityDescription(
        key="total_drive_distance",
        translation_key="total_drive_distance",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda data: data.statistics.total_drive_distance,
    ),
    AutomowerSensorEntityDescription(
        key="next_start_timestamp",
        translation_key="next_start_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.planner.next_start_dateteime,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor platform."""
    coordinator: AutomowerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AutomowerSensorEntity(mower_id, coordinator, description)
        for mower_id in coordinator.data
        for description in SENSOR_TYPES
        if description.exists_fn(coordinator.data[mower_id])
    )


class AutomowerSensorEntity(AutomowerBaseEntity, SensorEntity):
    """Defining the Automower Sensors with AutomowerSensorEntityDescription."""

    entity_description: AutomowerSensorEntityDescription

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        description: AutomowerSensorEntityDescription,
    ) -> None:
        """Set up AutomowerSensors."""
        super().__init__(mower_id, coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{mower_id}_{description.key}"

    @property
    def native_value(self) -> str | int | datetime.datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.mower_attributes)
