"""Sensor platform for the Google Health integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast, override

from google_health_api.model import PairedDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GoogleHealthConfigEntry
from .const import DOMAIN
from .coordinator import (
    GoogleHealthActivityCoordinator,
    GoogleHealthBodyCoordinator,
    GoogleHealthDataUpdateCoordinator,
    GoogleHealthDeviceCoordinator,
    GoogleHealthSleepCoordinator,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GoogleHealthSensorEntityDescription[
    _CoordinatorT: GoogleHealthDataUpdateCoordinator[Any],
    _ValueT: StateType,
](SensorEntityDescription):
    """Class describing Google Health sensor entities."""

    value_fn: Callable[[Any], _ValueT]


ACTIVITY_SENSORS: list[
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, Any]
] = [
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="steps",
        translation_key="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.steps.count_sum if data and data.steps else 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="distance",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.distance.millimeters_sum / 1000.0 if data and data.distance else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="active_calories",
        translation_key="active_calories",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.active_energy_burned.kcal_sum
            if data and data.active_energy_burned
            else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="total_calories",
        translation_key="total_calories",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.total_calories.kcal_sum if data and data.total_calories else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="floors",
        translation_key="floors",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.floors.count_sum if data and data.floors else 0,
    ),
]

BODY_SENSORS: list[
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, Any]
] = [
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="weight",
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.weight.weight_grams / 1000.0 if data and data.weight else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, int | None](
        key="resting_heart_rate",
        translation_key="resting_heart_rate",
        native_unit_of_measurement="bpm",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.resting_heart_rate.beats_per_minute
            if data and data.resting_heart_rate
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="body_fat",
        translation_key="body_fat",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.body_fat.percentage if data and data.body_fat else None
        ),
    ),
]

SLEEP_SENSORS: list[
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, Any]
] = [
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_asleep",
        translation_key="sleep_asleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sleep.summary.minutes_asleep
            if data and data.sleep and data.sleep.summary
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_awake",
        translation_key="sleep_awake",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sleep.summary.minutes_awake
            if data and data.sleep and data.sleep.summary
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_in_bed",
        translation_key="sleep_in_bed",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sleep.summary.minutes_in_sleep_period
            if data and data.sleep and data.sleep.summary
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_to_fall_asleep",
        translation_key="sleep_to_fall_asleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sleep.summary.minutes_to_fall_asleep
            if data and data.sleep and data.sleep.summary
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_after_wakeup",
        translation_key="sleep_after_wakeup",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.sleep.summary.minutes_after_wake_up
            if data and data.sleep and data.sleep.summary
            else None
        ),
    ),
]


@dataclass(frozen=True, kw_only=True)
class GoogleHealthDeviceSensorEntityDescription(SensorEntityDescription):
    """Class describing Google Health device sensor entities."""

    value_fn: Callable[[PairedDevice], datetime | StateType]


DEVICE_SENSORS: list[GoogleHealthDeviceSensorEntityDescription] = [
    GoogleHealthDeviceSensorEntityDescription(
        key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device.battery_level,
    ),
    GoogleHealthDeviceSensorEntityDescription(
        key="last_sync_time",
        translation_key="last_sync_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda device: (
            dt_util.parse_datetime(device.last_sync_time)
            if device.last_sync_time
            else None
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleHealthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Health sensor platform."""
    data = entry.runtime_data

    entities: list[SensorEntity] = []
    if (activity_coordinator := data.activity_coordinator) is not None:
        entities.extend(
            GoogleHealthSensor(activity_coordinator, entry.entry_id, description)
            for description in ACTIVITY_SENSORS
        )
    if (body_coordinator := data.body_coordinator) is not None:
        entities.extend(
            GoogleHealthSensor(body_coordinator, entry.entry_id, description)
            for description in BODY_SENSORS
        )
    if (sleep_coordinator := data.sleep_coordinator) is not None:
        entities.extend(
            GoogleHealthSensor(sleep_coordinator, entry.entry_id, description)
            for description in SLEEP_SENSORS
        )
    if entities:
        async_add_entities(entities)

    if (device_coordinator := data.device_coordinator) is not None:
        added_device_ids: set[str] = set()

        @callback
        def async_add_device_entities() -> None:
            """Add entities for new devices."""
            new_entities: list[SensorEntity] = []
            for device in device_coordinator.data.values():
                if device.device_id in added_device_ids:
                    continue
                added_device_ids.add(device.device_id)
                new_entities.extend(
                    GoogleHealthDeviceSensor(
                        device_coordinator,
                        entry.entry_id,
                        device,
                        description,
                    )
                    for description in DEVICE_SENSORS
                )
            if new_entities:
                async_add_entities(new_entities)

        async_add_device_entities()
        entry.async_on_unload(
            device_coordinator.async_add_listener(async_add_device_entities)
        )


class GoogleHealthSensor[_CoordinatorT: GoogleHealthDataUpdateCoordinator[Any]](
    CoordinatorEntity[_CoordinatorT], SensorEntity
):
    """Generic Google Health sensor entity."""

    _attr_has_entity_name = True
    entity_description: GoogleHealthSensorEntityDescription[_CoordinatorT, Any]

    def __init__(
        self,
        coordinator: _CoordinatorT,
        entry_id: str,
        description: GoogleHealthSensorEntityDescription[_CoordinatorT, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Google",
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return cast(StateType, self.entity_description.value_fn(self.coordinator.data))


class GoogleHealthDeviceSensor(
    CoordinatorEntity[GoogleHealthDeviceCoordinator], SensorEntity
):
    """Device-specific Google Health sensor entity."""

    _attr_has_entity_name = True
    entity_description: GoogleHealthDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: GoogleHealthDeviceCoordinator,
        entry_id: str,
        device: PairedDevice,
        description: GoogleHealthDeviceSensorEntityDescription,
    ) -> None:
        """Initialize the device sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self.device_id = device.device_id
        self._attr_unique_id = f"{device.device_id}_{description.key}"

        # device_version is the product name (e.g. 'Fitbit Charge 6', 'Pixel Watch 3')
        device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_version
            or (device.device_type.title() if device.device_type else "Device"),
            model=device.device_type.title() if device.device_type else None,
            sw_version=device.device_version,
            via_device=(DOMAIN, entry_id),
        )

        if device.mac_address:
            device_info["connections"] = {(CONNECTION_NETWORK_MAC, device.mac_address)}
        self._attr_device_info = device_info

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.device_id in self.coordinator.data

    @property
    @override
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        device = self.coordinator.data[self.device_id]
        return self.entity_description.value_fn(device)
