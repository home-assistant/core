"""Support for Anova Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from anova_wifi import AnovaMode, AnovaState, APCUpdateSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import AnovaDescriptionEntity
from .models import AnovaData


@dataclass(frozen=True)
class AnovaSensorEntityDescriptionMixin:
    """Describes the mixin variables for anova sensors."""

    value_fn: Callable[[APCUpdateSensor], float | int | str | None]


@dataclass(frozen=True)
class AnovaSensorEntityDescription(
    SensorEntityDescription, AnovaSensorEntityDescriptionMixin
):
    """Describes a Anova sensor."""


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
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Anova device."""
    anova_data: AnovaData = hass.data[DOMAIN][entry.entry_id]
    valid_entities: set[AnovaSensor] = set()
    ent_registry = er.async_get(hass)
    for coordinator in anova_data.coordinators:
        for description in SENSOR_DESCRIPTIONS:
            sensor = AnovaSensor(coordinator, description)
            if f"{DOMAIN}.{SENSOR_DOMAIN}_{sensor.unique_id}" in ent_registry.entities:
                # If the entity has been added before - we know it is supported.
                valid_entities.add(sensor)
            elif (
                coordinator.data is not None
                and description.value_fn(coordinator.data.sensor) is not None
            ):
                # If the coordinator has data and the value for this sensor is not None
                # then the entity is supported.
                # Device must be online for the first time it is added.
                valid_entities.add(sensor)
    if not valid_entities:
        raise PlatformNotReady(
            "No entities were available - if this is your first time setting up a Anova device in home assistant, make sure it is online."
        )
    async_add_entities(valid_entities)


class AnovaSensor(AnovaDescriptionEntity, SensorEntity):
    """A sensor using Anova coordinator."""

    entity_description: AnovaSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data.sensor)
