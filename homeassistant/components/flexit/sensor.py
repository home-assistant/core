"""Sensor platform for the Flexit integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from flexit_modbus import Measurements

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import FlexitConfigEntry, FlexitDataCoordinator
from .entity import FlexitEntity


@dataclass(kw_only=True, frozen=True)
class FlexitSensorEntityDescription(SensorEntityDescription):
    """Describe a Flexit sensor entity."""

    value_fn: Callable[[Measurements], StateType]


SENSORS: tuple[FlexitSensorEntityDescription, ...] = (
    FlexitSensorEntityDescription(
        key="air_filter_operating_time",
        translation_key="air_filter_operating_time",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda measurements: measurements.filter_running_hours,
    ),
    FlexitSensorEntityDescription(
        key="heat_exchanger_regulation",
        translation_key="heat_exchanger_regulation",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda measurements: measurements.heat_exchanger_regulation,
    ),
    FlexitSensorEntityDescription(
        key="electric_heater_regulation",
        translation_key="electric_heater_regulation",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda measurements: measurements.electric_heater_regulation,
    ),
    FlexitSensorEntityDescription(
        key="cooling_regulation",
        translation_key="cooling_regulation",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda measurements: measurements.cooling_regulation,
    ),
    FlexitSensorEntityDescription(
        key="outdoor_air_temperature",
        translation_key="outdoor_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda measurements: measurements.outdoor_air_temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlexitConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flexit sensor entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FlexitSensor(coordinator, description) for description in SENSORS
    )


class FlexitSensor(FlexitEntity, SensorEntity):
    """Representation of a Flexit sensor."""

    entity_description: FlexitSensorEntityDescription

    def __init__(
        self,
        coordinator: FlexitDataCoordinator,
        entity_description: FlexitSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        assert coordinator.config_entry is not None
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}-{entity_description.key}"
        )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.device.measurements)
