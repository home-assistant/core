"""Sensor platform for the Google Health integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast, override

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
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GoogleHealthConfigEntry
from .const import DOMAIN, HealthApiScope
from .coordinator import (
    GoogleHealthActivityCoordinator,
    GoogleHealthBodyCoordinator,
    GoogleHealthDataUpdateCoordinator,
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
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="hydration",
        translation_key="hydration",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.hydration.amount_consumed.milliliters_sum / 1000.0
            if data and data.hydration and data.hydration.amount_consumed
            else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="calories_consumed",
        translation_key="calories_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.nutrition.energy.kcal_sum
            if data and data.nutrition and data.nutrition.energy
            else 0.0
        ),
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleHealthConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Google Health sensor platform."""
    data = entry.runtime_data
    scopes = entry.data.get("token", {}).get("scope", "").split()
    nutrition_keys = {"hydration", "calories_consumed"}

    entities: list[SensorEntity] = []
    if (activity_coordinator := data.activity_coordinator) is not None:
        entities.extend(
            GoogleHealthSensor(activity_coordinator, entry.entry_id, description)
            for description in ACTIVITY_SENSORS
            if description.key not in nutrition_keys
            or HealthApiScope.NUTRITION_READ in scopes
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
