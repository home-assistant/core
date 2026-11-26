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
    EntityCategory,
    UnitOfArea,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfTime,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntryType,
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM, UnitSystem

from . import GoogleHealthConfigEntry
from .const import DOMAIN
from .coordinator import (
    GoogleHealthActivityCoordinator,
    GoogleHealthBodyCoordinator,
    GoogleHealthDataUpdateCoordinator,
    GoogleHealthDeviceCoordinator,
    GoogleHealthNutritionCoordinator,
    GoogleHealthNutritionData,
    GoogleHealthSleepCoordinator,
    GoogleHealthSleepData,
)

PARALLEL_UPDATES = 0


def _sleep_stage_minutes(
    data: GoogleHealthSleepData | None, stage_type: str
) -> int | None:
    """Return duration in minutes for a sleep stage type."""
    if (
        not data
        or not data.sleep
        or not data.sleep.summary
        or not data.sleep.summary.stages_summary
    ):
        return None
    return next(
        (
            stage.minutes
            for stage in data.sleep.summary.stages_summary
            if stage.type == stage_type
        ),
        None,
    )


def _nutrient_grams(data: GoogleHealthNutritionData | None, nutrient: str) -> float:
    """Return daily intake in grams for a nutrient type."""
    if not data or not data.nutrition:
        return 0.0
    return next(
        (
            item.quantity.grams_sum
            for item in data.nutrition.nutrients
            if item.nutrient == nutrient
        ),
        0.0,
    )


@dataclass(frozen=True, kw_only=True)
class GoogleHealthSensorEntityDescription[
    _CoordinatorT: GoogleHealthDataUpdateCoordinator[Any],
    _ValueT: datetime | StateType,
](SensorEntityDescription):
    """Class describing Google Health sensor entities."""

    value_fn: Callable[[Any], _ValueT]
    suggested_unit_fn: Callable[[UnitSystem], str | None] | None = None
    last_reset_fn: Callable[[Any], datetime | None] | None = None


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
        suggested_unit_fn=lambda units: (
            UnitOfLength.MILES
            if units is US_CUSTOMARY_SYSTEM
            else UnitOfLength.KILOMETERS
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="active_calories",
        translation_key="active_calories",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        device_class=SensorDeviceClass.ENERGY,
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
        device_class=SensorDeviceClass.ENERGY,
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
        key="elevation",
        translation_key="elevation",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.TOTAL,
        value_fn=lambda data: (data.altitude_gain_millimeters or 0) / 1000.0,
        last_reset_fn=lambda data: data.rollup_start,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="light_activity",
        translation_key="light_activity",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.light_activity_minutes or 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="moderate_activity",
        translation_key="moderate_activity",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.moderate_activity_minutes or 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="vigorous_activity",
        translation_key="vigorous_activity",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.vigorous_activity_minutes or 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="active_zone_minutes",
        translation_key="active_zone_minutes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.total_active_zone_minutes or 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, float](
        key="sedentary_time",
        translation_key="sedentary_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.sedentary_duration.total_seconds() if data.sedentary_duration else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="fat_burn_active_zone_minutes",
        translation_key="fat_burn_active_zone_minutes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.fat_burn_active_zone_minutes or 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="cardio_active_zone_minutes",
        translation_key="cardio_active_zone_minutes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.cardio_active_zone_minutes or 0,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthActivityCoordinator, int](
        key="peak_active_zone_minutes",
        translation_key="peak_active_zone_minutes",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.peak_active_zone_minutes or 0,
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
        suggested_unit_fn=lambda units: (
            UnitOfMass.POUNDS if units is US_CUSTOMARY_SYSTEM else None
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
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="heart_rate_variability",
        translation_key="heart_rate_variability",
        native_unit_of_measurement=UnitOfTime.MILLISECONDS,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.heart_rate_variability.average_heart_rate_variability_milliseconds
            if data and data.heart_rate_variability
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="oxygen_saturation",
        translation_key="oxygen_saturation",
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.oxygen_saturation.average_percentage
            if data and data.oxygen_saturation
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="respiratory_rate",
        translation_key="respiratory_rate",
        native_unit_of_measurement="br/min",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: (
            data.respiratory_rate.breaths_per_minute
            if data and data.respiratory_rate
            else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="height",
        translation_key="height",
        # Meters auto-convert to feet in US customary
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.height.height_millimeters / 1000.0 if data and data.height else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="body_mass_index",
        translation_key="body_mass_index",
        native_unit_of_measurement=f"{UnitOfMass.KILOGRAMS}/{UnitOfArea.SQUARE_METERS}",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.bmi.bmi if data and data.bmi else None,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthBodyCoordinator, float | None](
        key="vo2_max",
        translation_key="vo2_max",
        native_unit_of_measurement="ml/min/kg",
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.vo2_max.vo2_max if data and data.vo2_max else None,
    ),
]

SLEEP_SENSORS: list[
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, Any]
] = [
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_asleep",
        translation_key="sleep_asleep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
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
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
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
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
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
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, datetime | None](
        key="sleep_start_time",
        translation_key="sleep_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.sleep.start_time if data and data.sleep else None,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, datetime | None](
        key="sleep_end_time",
        translation_key="sleep_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.sleep.end_time if data and data.sleep else None,
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_rem",
        translation_key="sleep_rem",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _sleep_stage_minutes(data, "REM"),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_deep",
        translation_key="sleep_deep",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _sleep_stage_minutes(data, "DEEP"),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthSleepCoordinator, int | None](
        key="sleep_light",
        translation_key="sleep_light",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _sleep_stage_minutes(data, "LIGHT"),
    ),
]


NUTRITION_SENSORS: list[
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, Any]
] = [
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
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
        suggested_unit_fn=lambda units: (
            UnitOfVolume.FLUID_OUNCES if units is US_CUSTOMARY_SYSTEM else None
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="calories_consumed",
        translation_key="calories_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.nutrition.energy.kcal_sum
            if data and data.nutrition and data.nutrition.energy
            else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="total_fat",
        translation_key="total_fat",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.nutrition.total_fat.grams_sum
            if data and data.nutrition and data.nutrition.total_fat
            else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="total_carbohydrate",
        translation_key="total_carbohydrate",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: (
            data.nutrition.total_carbohydrate.grams_sum
            if data and data.nutrition and data.nutrition.total_carbohydrate
            else 0.0
        ),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="protein",
        translation_key="protein",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: _nutrient_grams(data, "PROTEIN"),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="dietary_fiber",
        translation_key="dietary_fiber",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _nutrient_grams(data, "DIETARY_FIBER"),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="sugar",
        translation_key="sugar",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_display_precision=1,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _nutrient_grams(data, "SUGAR"),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="sodium",
        translation_key="sodium",
        native_unit_of_measurement=UnitOfMass.GRAMS,
        suggested_unit_of_measurement=UnitOfMass.MILLIGRAMS,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.WEIGHT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _nutrient_grams(data, "SODIUM"),
    ),
    GoogleHealthSensorEntityDescription[GoogleHealthNutritionCoordinator, float](
        key="calories_from_fat",
        translation_key="calories_from_fat",
        native_unit_of_measurement=UnitOfEnergy.KILO_CALORIE,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        value_fn=lambda data: (
            data.nutrition.energy_from_fat.kcal_sum
            if data and data.nutrition and data.nutrition.energy_from_fat
            else 0.0
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
        value_fn=lambda device: device.last_sync_time,
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
    if (nutrition_coordinator := data.nutrition_coordinator) is not None:
        entities.extend(
            GoogleHealthSensor(nutrition_coordinator, entry.entry_id, description)
            for description in NUTRITION_SENSORS
        )
    if entities:
        async_add_entities(entities)

    if (device_coordinator := data.device_coordinator) is not None:
        added_device_ids: set[str] = set()

        @callback
        def async_add_device_entities() -> None:
            """Add entities for new devices and remove stale devices."""
            current_device_ids = set(device_coordinator.data)
            # Drop any devices no longer present in the API. They will be removed below
            added_device_ids.intersection_update(current_device_ids)

            # Add any newly discovered devices
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

            # Remove any stale devices
            device_registry = dr.async_get(hass)
            active_identifiers = {(DOMAIN, entry.entry_id)} | {
                (DOMAIN, device_id) for device_id in current_device_ids
            }
            for device_entry in dr.async_entries_for_config_entry(
                device_registry, entry.entry_id
            ):
                if not set(device_entry.identifiers) & active_identifiers:
                    device_registry.async_remove_device(device_entry.id)

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
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            manufacturer="Google",
        )

    @property
    @override
    def native_value(self) -> datetime | StateType:
        """Return the state of the sensor."""
        return cast(
            datetime | StateType,
            self.entity_description.value_fn(self.coordinator.data),
        )

    @property
    @override
    def suggested_unit_of_measurement(self) -> str | None:
        """Return the suggested unit of measurement."""
        if (suggested_unit_fn := self.entity_description.suggested_unit_fn) is not None:
            return suggested_unit_fn(self.hass.config.units)

        return super().suggested_unit_of_measurement

    @property
    @override
    def last_reset(self) -> datetime | None:
        """Return the time when the sensor was last reset, if any."""
        if (last_reset_fn := self.entity_description.last_reset_fn) is not None:
            return last_reset_fn(self.coordinator.data)

        return super().last_reset


class GoogleHealthDeviceSensor(
    CoordinatorEntity[GoogleHealthDeviceCoordinator], SensorEntity
):
    """Device-specific Google Health sensor entity."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
            via_device_id=async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, entry_id),
                config_entry_id=entry_id,
            ),
        )

        if device.mac_address:
            device_info.connections = {(CONNECTION_NETWORK_MAC, device.mac_address)}
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
