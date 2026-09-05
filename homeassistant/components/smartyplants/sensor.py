"""Sensor entities for SmartyPlants."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pysmartyplants import Reading, Readings, Sensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SmartyPlantsConfigEntry, SmartyPlantsCoordinator
from .entity import SmartyPlantsEntity

# Read-only and coordinator-driven, so updates need not be serialised.
PARALLEL_UPDATES = 0


def _metric(pick: Callable[[Readings], Reading]) -> Callable[[Sensor], float | None]:
    """Build the value function for one reading block.

    A metric the backend is still working out reports nothing, rather than a
    placeholder the user would read as a measurement.
    """

    def value(sensor: Sensor) -> float | None:
        if sensor.readings is None:
            return None
        reading = pick(sensor.readings)
        return None if reading.is_calculating else reading.value

    return value


def _fertilise_days(sensor: Sensor) -> float | None:
    """Return how long until the plant is due to be fed."""
    if sensor.readings is None or sensor.readings.fertiliser.is_calculating:
        return None
    return sensor.readings.fertiliser.days_until_fertilise


def _health_score(sensor: Sensor) -> float | None:
    """Return the overall score the backend derived for this plant."""
    return sensor.health.score if sensor.health is not None else None


def _battery(sensor: Sensor) -> float | None:
    """Prefer the battery reading, falling back to the sensor's own level."""
    if sensor.readings is not None and sensor.readings.battery.value is not None:
        return sensor.readings.battery.value
    return sensor.battery_percentage


def _temperature_unit(sensor: Sensor) -> str | None:
    """Follow the unit the user chose in the SmartyPlants app."""
    if sensor.readings is not None and sensor.readings.temperature.unit == "°F":
        return UnitOfTemperature.FAHRENHEIT
    return UnitOfTemperature.CELSIUS


@dataclass(frozen=True, kw_only=True)
class SmartyPlantsSensorDescription(SensorEntityDescription):
    """Describes one SmartyPlants sensor entity."""

    value_fn: Callable[[Sensor], float | None]
    # Set where the backend reports the unit alongside the reading.
    unit_fn: Callable[[Sensor], str | None] | None = None


SENSOR_TYPES: tuple[SmartyPlantsSensorDescription, ...] = (
    SmartyPlantsSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=_temperature_unit,
        value_fn=_metric(lambda readings: readings.temperature),
    ),
    SmartyPlantsSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_metric(lambda readings: readings.humidity),
    ),
    SmartyPlantsSensorDescription(
        key="moisture",
        translation_key="moisture",
        device_class=SensorDeviceClass.MOISTURE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_metric(lambda readings: readings.moisture),
    ),
    SmartyPlantsSensorDescription(
        key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        value_fn=_metric(lambda readings: readings.light),
    ),
    SmartyPlantsSensorDescription(
        key="light_quality",
        translation_key="light_quality",
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_metric(lambda readings: readings.light_quality),
    ),
    SmartyPlantsSensorDescription(
        key="health_score",
        translation_key="health_score",
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=_health_score,
    ),
    SmartyPlantsSensorDescription(
        key="fertilise_days",
        translation_key="fertilise_days",
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=_fertilise_days,
    ),
    SmartyPlantsSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_battery,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyPlantsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one set of sensor entities per physical sensor."""
    coordinator = entry.runtime_data

    async_add_entities(
        SmartyPlantsSensor(coordinator, sensor_id, description)
        for sensor_id in coordinator.data
        for description in SENSOR_TYPES
    )


class SmartyPlantsSensor(SmartyPlantsEntity, SensorEntity):
    """A single metric on a single SmartyPlants sensor."""

    entity_description: SmartyPlantsSensorDescription

    def __init__(
        self,
        coordinator: SmartyPlantsCoordinator,
        sensor_id: str,
        description: SmartyPlantsSensorDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator, sensor_id)
        self.entity_description = description
        self._attr_unique_id = f"{sensor_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._update_unit()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Pick up the unit alongside the new readings."""
        self._update_unit()
        super()._handle_coordinator_update()

    @callback
    def _update_unit(self) -> None:
        """Follow the unit the backend reports for this reading.

        Held as an attribute rather than read on demand because the unit is
        part of the entity's capabilities, which Home Assistant reads even
        while the sensor is unavailable and has no readings to consult.
        """
        if (unit_fn := self.entity_description.unit_fn) is not None:
            if self._sensor_id in self.coordinator.data:
                self._attr_native_unit_of_measurement = unit_fn(self.sensor)

    @property
    @override
    def native_value(self) -> float | None:
        """Return the current value for this metric."""
        return self.entity_description.value_fn(self.sensor)
