"""Support for Anova Sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from anova_wifi import APCUpdateSensor

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .entity import AnovaDescriptionEntity
from .models import AnovaData


@dataclass
class AnovaSensorEntityDescriptionMixin:
    """Describes the mixin variables for anova sensors."""

    value_fn: Callable[[APCUpdateSensor], float | int | str]


@dataclass
class AnovaSensorEntityDescription(
    SensorEntityDescription, AnovaSensorEntityDescriptionMixin
):
    """Describes a Anova sensor."""


SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    AnovaSensorEntityDescription(
        key="cook_time",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="cook_time",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.cook_time,
    ),
    AnovaSensorEntityDescription(
        key="state", translation_key="state", value_fn=lambda data: data.state
    ),
    AnovaSensorEntityDescription(
        key="mode", translation_key="mode", value_fn=lambda data: data.mode
    ),
    AnovaSensorEntityDescription(
        key="target_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="target_temperature",
        value_fn=lambda data: data.target_temperature,
    ),
    AnovaSensorEntityDescription(
        key="cook_time_remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key="cook_time_remaining",
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.cook_time_remaining,
    ),
    AnovaSensorEntityDescription(
        key="heater_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="heater_temperature",
        value_fn=lambda data: data.heater_temperature,
    ),
    AnovaSensorEntityDescription(
        key="triac_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key="triac_temperature",
        value_fn=lambda data: data.triac_temperature,
    ),
    AnovaSensorEntityDescription(
        key="water_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
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
    async_add_entities(
        AnovaSensor(coordinator, description)
        for coordinator in anova_data.coordinators
        for description in SENSOR_DESCRIPTIONS
    )


class AnovaSensor(AnovaDescriptionEntity, SensorEntity):
    """A sensor using Anova coordinator."""

    entity_description: AnovaSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data.sensor)
