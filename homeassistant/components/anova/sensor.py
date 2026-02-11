"""Support for Anova Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from anova_wifi import AnovaMode, AnovaState, APCUpdateSensor

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import AnovaConfigEntry, AnovaCoordinator
from .entity import AnovaDescriptionEntity


@dataclass(frozen=True, kw_only=True)
class AnovaSensorEntityDescription(SensorEntityDescription):
    """Describes a Anova sensor."""

    value_fn: Callable[[APCUpdateSensor], StateType]


SENSOR_DESCRIPTIONS: list[AnovaSensorEntityDescription] = [
    AnovaSensorEntityDescription(
        key="cook_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        translation_key="cook_time",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.cook_time,
    ),
    AnovaSensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.name for state in AnovaState],
        value_fn=lambda data: data.state,
    ),
    AnovaSensorEntityDescription(
        key="mode",
        translation_key="mode",
        device_class=SensorDeviceClass.ENUM,
        options=[mode.name for mode in AnovaMode],
        value_fn=lambda data: data.mode,
    ),
    AnovaSensorEntityDescription(
        key="target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="target_temperature",
        value_fn=lambda data: data.target_temperature,
    ),
    AnovaSensorEntityDescription(
        key="cook_time_remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        translation_key="cook_time_remaining",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.cook_time_remaining,
    ),
    AnovaSensorEntityDescription(
        key="heater_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="heater_temperature",
        value_fn=lambda data: data.heater_temperature,
    ),
    AnovaSensorEntityDescription(
        key="triac_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="triac_temperature",
        value_fn=lambda data: data.triac_temperature,
    ),
    AnovaSensorEntityDescription(
        key="water_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key="water_temperature",
        value_fn=lambda data: data.water_temperature,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AnovaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Anova device."""
    anova_data = entry.runtime_data

    for coordinator in anova_data.coordinators:
        setup_coordinator(coordinator, async_add_entities)


def setup_coordinator(
    coordinator: AnovaCoordinator,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an individual Anova Coordinator."""

    def _async_sensor_listener() -> None:
        """Listen for new sensor data and add sensors if they did not exist."""
        if not coordinator.sensor_data_set:
            valid_entities: set[AnovaSensor] = set()
            for description in SENSOR_DESCRIPTIONS:
                if description.value_fn(coordinator.data.sensor) is not None:
                    valid_entities.add(AnovaSensor(coordinator, description))
            async_add_entities(valid_entities)
            coordinator.sensor_data_set = True

    if coordinator.data is not None:
        _async_sensor_listener()
    # It is possible that we don't have any data, but the device exists,
    # i.e. slow network, offline device, etc.
    # We want to set up sensors after the fact as we don't know what sensors
    # are valid until runtime.
    coordinator.async_add_listener(_async_sensor_listener)


class AnovaSensor(AnovaDescriptionEntity, SensorEntity):
    """A sensor using Anova coordinator."""

    entity_description: AnovaSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data.sensor)
