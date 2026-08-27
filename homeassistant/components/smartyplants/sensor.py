"""Sensor entities for SmartyPlants."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, override

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import STATUS_OPTIONS
from .coordinator import (
    SmartyPlantsConfigEntry,
    SmartyPlantsCoordinator,
    last_reported,
    setup_status,
)
from .entity import SmartyPlantsEntity, async_setup_dynamic_entities

# Read-only and coordinator-driven, so updates need not be serialised.
PARALLEL_UPDATES = 0


def _numeric(value: Any) -> int | float | None:
    """Return the value only when it is genuinely a number.

    The backend can send a placeholder such as "-" for a metric it could not
    compute. Home Assistant refuses a non-numeric state on a measurement
    entity and raises, so anything unparsable becomes unknown instead.

    Numbers are returned as they arrived, so an integer reading is not
    reported as a float.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _reading(sensor: dict[str, Any], key: str) -> float | None:
    """Pull a numeric reading, withholding it while the metric is calculating."""
    block = (sensor.get("readings") or {}).get(key) or {}
    if block.get("isCalculating"):
        return None
    return _numeric(block.get("value"))


@dataclass(frozen=True, kw_only=True)
class SmartyPlantsSensorDescription(SensorEntityDescription):
    """Describes one SmartyPlants sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType | datetime]
    unit_fn: Callable[[dict[str, Any]], str | None] | None = None
    # Readings block backing this entity, when it differs from the entity key.
    readings_key: str | None = None
    # Diagnostics stay visible when readings go stale, so the user can see why.
    stale_sensitive: bool = True
    # Skipped for plants that have no sensor, where the metric has no meaning.
    requires_sensor: bool = True


SENSOR_TYPES: tuple[SmartyPlantsSensorDescription, ...] = (
    SmartyPlantsSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        # The backend honours the user's preferred unit, so read it per update.
        unit_fn=lambda sensor: (
            UnitOfTemperature.FAHRENHEIT
            if ((sensor.get("readings") or {}).get("temperature") or {}).get("unit")
            == "°F"
            else UnitOfTemperature.CELSIUS
        ),
        value_fn=lambda sensor: _reading(sensor, "temperature"),
    ),
    SmartyPlantsSensorDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda sensor: _reading(sensor, "humidity"),
    ),
    SmartyPlantsSensorDescription(
        key="moisture",
        translation_key="moisture",
        device_class=SensorDeviceClass.MOISTURE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda sensor: _reading(sensor, "moisture"),
    ),
    SmartyPlantsSensorDescription(
        key="light",
        device_class=SensorDeviceClass.ILLUMINANCE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=LIGHT_LUX,
        value_fn=lambda sensor: _reading(sensor, "light"),
    ),
    SmartyPlantsSensorDescription(
        key="light_quality",
        translation_key="light_quality",
        suggested_display_precision=0,
        readings_key="lightQuality",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda sensor: _reading(sensor, "lightQuality"),
    ),
    SmartyPlantsSensorDescription(
        key="health_score",
        translation_key="health_score",
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda sensor: _numeric((sensor.get("health") or {}).get("score")),
    ),
    SmartyPlantsSensorDescription(
        key="fertilise_days",
        translation_key="fertilise_days",
        suggested_display_precision=0,
        readings_key="fertiliser",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda sensor: (
            None
            if ((sensor.get("readings") or {}).get("fertiliser") or {}).get(
                "isCalculating"
            )
            else _numeric(
                ((sensor.get("readings") or {}).get("fertiliser") or {}).get(
                    "daysUntilFertilise"
                )
            )
        ),
    ),
    # Diagnostics below: these describe the sensor itself, so they must keep
    # reporting once the readings are no longer trustworthy.
    SmartyPlantsSensorDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        stale_sensitive=False,
        value_fn=lambda sensor: _numeric(
            ((sensor.get("readings") or {}).get("battery") or {}).get(
                "value", sensor.get("batteryPercentage")
            )
        ),
    ),
    SmartyPlantsSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        stale_sensitive=False,
        requires_sensor=False,
        value_fn=setup_status,
    ),
    SmartyPlantsSensorDescription(
        key="last_reported",
        translation_key="last_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        # Useful when chasing a problem, noise the rest of the time: the
        # status and connectivity entities already say whether data is
        # arriving.
        entity_registry_enabled_default=False,
        stale_sensitive=False,
        value_fn=last_reported,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyPlantsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one set of sensor entities per physical sensor."""
    coordinator = entry.runtime_data

    async_setup_dynamic_entities(
        entry,
        coordinator,
        async_add_entities,
        lambda sensor_id: (
            SmartyPlantsSensor(coordinator, sensor_id, description)
            for description in SENSOR_TYPES
            if description.requires_sensor is False
            or not coordinator.data[sensor_id].get("isPlantOnly")
        ),
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

    @property
    @override
    def available(self) -> bool:
        """Follow the shared availability rule for this entity's description."""
        return self._availability_for(
            stale_sensitive=self.entity_description.stale_sensitive,
            requires_sensor=self.entity_description.requires_sensor,
        )

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Prefer the unit reported by the backend when one is supplied."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.sensor)
        return super().native_unit_of_measurement

    @property
    @override
    def native_value(self) -> StateType | datetime:
        """Return the current value for this metric."""
        return self.entity_description.value_fn(self.sensor)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the optimal band and status so users can build alerts on it."""
        description = self.entity_description
        block = self.readings.get(description.readings_key or description.key)
        if not isinstance(block, dict):
            return None

        attributes: dict[str, Any] = {}
        if (status := block.get("status")) is not None:
            attributes["status"] = status
        if isinstance(optimal := block.get("optimalRange"), dict):
            attributes["optimal_low"] = optimal.get("low")
            attributes["optimal_high"] = optimal.get("high")

        return attributes or None
