"""Support for switch entities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from gardena_bluetooth.const import (
    AquaContourBattery,
    Battery,
    EventHistory,
    FlowStatistics,
    Sensor,
    Spray,
    Valve,
)
from gardena_bluetooth.parse import Characteristic

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
    StateType,
)
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    EntityCategory,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import GardenaBluetoothConfigEntry, GardenaBluetoothCoordinator
from .entity import GardenaBluetoothDescriptorEntity, GardenaBluetoothEntity

type SensorRawType = StateType | datetime


def _get_timestamp(value: datetime | None):
    if value is None:
        return None
    return value.replace(tzinfo=dt_util.get_default_time_zone())


def _get_distance_ratio(value: int | None):
    if value is None:
        return None
    return value / 1000


@dataclass(frozen=True)
class GardenaBluetoothSensorEntityDescription[T](SensorEntityDescription):
    """Description of entity."""

    char: Characteristic[T] = field(default_factory=lambda: Characteristic(""))
    connected_state: Characteristic | None = None
    get: Callable[[T | None], SensorRawType] = lambda x: x  # type: ignore[assignment, return-value]

    @property
    def context(self) -> set[str]:
        """Context needed for update coordinator."""
        data = {self.char.uuid}
        if self.connected_state:
            data.add(self.connected_state.uuid)
        return data


DESCRIPTIONS = (
    GardenaBluetoothSensorEntityDescription(
        key=Valve.activation_reason.unique_id,
        translation_key="activation_reason",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        char=Valve.activation_reason,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Battery.battery_level.unique_id,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        char=Battery.battery_level,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=AquaContourBattery.battery_level.unique_id,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        char=AquaContourBattery.battery_level,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.battery_level.unique_id,
        translation_key="sensor_battery_level",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        char=Sensor.battery_level,
        connected_state=Sensor.connected_state,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.value.unique_id,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        char=Sensor.value,
        connected_state=Sensor.connected_state,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.type.unique_id,
        translation_key="sensor_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Sensor.type,
        connected_state=Sensor.connected_state,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.measurement_timestamp.unique_id,
        translation_key="sensor_measurement_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Sensor.measurement_timestamp,
        connected_state=Sensor.connected_state,
        get=_get_timestamp,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=FlowStatistics.overall.unique_id,
        translation_key="flow_statistics_overall",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.VOLUME,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        char=FlowStatistics.overall,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=FlowStatistics.current.unique_id,
        translation_key="flow_statistics_current",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        char=FlowStatistics.current,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=FlowStatistics.resettable.unique_id,
        translation_key="flow_statistics_resettable",
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.VOLUME,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        char=FlowStatistics.resettable,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=FlowStatistics.last_reset.unique_id,
        translation_key="flow_statistics_reset_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        char=FlowStatistics.last_reset,
        get=_get_timestamp,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Spray.current_distance.unique_id,
        translation_key="spray_current_distance",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        char=Spray.current_distance,
        get=_get_distance_ratio,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Spray.current_sector.unique_id,
        translation_key="spray_current_sector",
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=DEGREE,
        char=Spray.current_sector,
    ),
    GardenaBluetoothSensorEntityDescription(
        key="aqua_contour_error",
        translation_key="aqua_contour_error",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.ENUM,
        char=EventHistory.error,
        get=lambda x: (
            x.error_code.name.lower()
            if x and isinstance(x.error_code, EventHistory.error.enum)
            else None
        ),
        options=[member.name.lower() for member in EventHistory.error.enum],
    ),
    GardenaBluetoothSensorEntityDescription(
        key="aqua_contour_error_timestamp",
        translation_key="error_timestamp",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        char=EventHistory.error,
        get=lambda x: _get_timestamp(x.time_stamp) if x else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenaBluetoothConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Gardena Bluetooth sensor based on a config entry."""
    coordinator = entry.runtime_data
    entities: list[GardenaBluetoothEntity] = [
        GardenaBluetoothSensor(coordinator, description, description.context)
        for description in DESCRIPTIONS
        if description.char.unique_id in coordinator.characteristics
    ]
    if Valve.remaining_open_time.unique_id in coordinator.characteristics:
        entities.append(GardenaBluetoothRemainSensor(coordinator))
    async_add_entities(entities)


class GardenaBluetoothSensor(GardenaBluetoothDescriptorEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: GardenaBluetoothSensorEntityDescription

    def _handle_coordinator_update(self) -> None:
        value = self.coordinator.get_cached(self.entity_description.char)
        value = self.entity_description.get(value)
        self._attr_native_value = value

        if char := self.entity_description.connected_state:
            self._attr_available = bool(self.coordinator.get_cached(char))
        else:
            self._attr_available = True

        super()._handle_coordinator_update()


class GardenaBluetoothRemainSensor(GardenaBluetoothEntity, SensorEntity):
    """Representation of a sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_native_value: datetime | None = None
    _attr_translation_key = "remaining_open_timestamp"

    def __init__(
        self,
        coordinator: GardenaBluetoothCoordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, {Valve.remaining_open_time.uuid})
        self._attr_unique_id = f"{coordinator.address}-remaining_open_timestamp"

    def _handle_coordinator_update(self) -> None:
        value = self.coordinator.get_cached(Valve.remaining_open_time)
        if not value:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return

        time = datetime.now(UTC) + timedelta(seconds=value)
        if not self._attr_native_value:
            self._attr_native_value = time
            super()._handle_coordinator_update()
            return

        error = time - self._attr_native_value
        if abs(error.total_seconds()) > 10:
            self._attr_native_value = time
            super()._handle_coordinator_update()
            return

    @property
    def available(self) -> bool:
        """Sensor only available when open."""
        return super().available and self._attr_native_value is not None
