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

# Define constants for string literals
SENSOR_KEY_COOK_TIME = "cook_time"
SENSOR_KEY_STATE = "state"
SENSOR_KEY_MODE = "mode"
SENSOR_KEY_TARGET_TEMPERATURE = "target_temperature"
SENSOR_KEY_COOK_TIME_REMAINING = "cook_time_remaining"
SENSOR_KEY_HEATER_TEMPERATURE = "heater_temperature"
SENSOR_KEY_TRIAC_TEMPERATURE = "triac_temperature"
SENSOR_KEY_WATER_TEMPERATURE = "water_temperature"


@dataclass
class AnovaSensorEntityDescriptionMixin:
    """Describes the mixin variables for Anova sensors."""

    value_fn: Callable[[APCUpdateSensor], float | int | str]


@dataclass
class AnovaSensorEntityDescription(
    SensorEntityDescription, AnovaSensorEntityDescriptionMixin
):
    """Describes a Anova sensor."""


# List of sensor descriptions using constants
SENSOR_DESCRIPTIONS: list[SensorEntityDescription] = [
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_COOK_TIME,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key=SENSOR_KEY_COOK_TIME,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.cook_time,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_STATE,
        translation_key=SENSOR_KEY_STATE,
        value_fn=lambda data: data.state,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_MODE,
        translation_key=SENSOR_KEY_MODE,
        value_fn=lambda data: data.mode,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key=SENSOR_KEY_TARGET_TEMPERATURE,
        value_fn=lambda data: data.target_temperature,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_COOK_TIME_REMAINING,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:clock-outline",
        translation_key=SENSOR_KEY_COOK_TIME_REMAINING,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda data: data.cook_time_remaining,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_HEATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key=SENSOR_KEY_HEATER_TEMPERATURE,
        value_fn=lambda data: data.heater_temperature,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_TRIAC_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key=SENSOR_KEY_TRIAC_TEMPERATURE,
        value_fn=lambda data: data.triac_temperature,
    ),
    AnovaSensorEntityDescription(
        key=SENSOR_KEY_WATER_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        translation_key=SENSOR_KEY_WATER_TEMPERATURE,
        value_fn=lambda data: data.water_temperature,
    ),
]

# ... (other code)


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
