"""Sensor platform for La Marzocco espresso machines."""

from collections.abc import Callable
from dataclasses import dataclass

from lmcloud import LMCloud as LaMarzoccoClient

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import LaMarzoccoEntity, LaMarzoccoEntityDescription


@dataclass(frozen=True, kw_only=True)
class LaMarzoccoSensorEntityDescription(
    LaMarzoccoEntityDescription,
    SensorEntityDescription,
):
    """Description of a La Marzocco sensor."""

    value_fn: Callable[[LaMarzoccoClient], float | int]


ENTITIES: tuple[LaMarzoccoSensorEntityDescription, ...] = (
    LaMarzoccoSensorEntityDescription(
        key="drink_stats_coffee",
        translation_key="drink_stats_coffee",
        icon="mdi:chart-line",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lm: lm.current_status.get("drinks_k1", 0),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription(
        key="drink_stats_flushing",
        translation_key="drink_stats_flushing",
        icon="mdi:chart-line",
        native_unit_of_measurement="drinks",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda lm: lm.current_status.get("total_flushing", 0),
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription(
        key="shot_timer",
        translation_key="shot_timer",
        icon="mdi:timer",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.DURATION,
        value_fn=lambda lm: lm.current_status.get("brew_active_duration", 0),
        available_fn=lambda lm: lm.websocket_connected,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    LaMarzoccoSensorEntityDescription(
        key="current_temp_coffee",
        translation_key="current_temp_coffee",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda lm: lm.current_status.get("coffee_temp", 0),
    ),
    LaMarzoccoSensorEntityDescription(
        key="current_temp_steam",
        translation_key="current_temp_steam",
        icon="mdi:thermometer",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
        value_fn=lambda lm: lm.current_status.get("steam_temp", 0),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[LaMarzoccoSensorEntity] = []
    for description in ENTITIES:
        if coordinator.lm.model_name in description.supported_models:
            if description.key == "shot_timer" and not config_entry.data.get(CONF_HOST):
                continue
            entities.append(LaMarzoccoSensorEntity(coordinator, description))

    async_add_entities(entities)


class LaMarzoccoSensorEntity(LaMarzoccoEntity, SensorEntity):
    """Sensor representing espresso machine temperature data."""

    entity_description: LaMarzoccoSensorEntityDescription

    @property
    def native_value(self) -> int | float:
        """State of the sensor."""
        return self.entity_description.value_fn(self.coordinator.lm)
