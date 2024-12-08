"""Support for Salda Smarty XP/XV Ventilation Unit Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from pysmarty2 import Smarty

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import REVOLUTIONS_PER_MINUTE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .coordinator import SmartyConfigEntry, SmartyCoordinator
from .entity import SmartyEntity

_LOGGER = logging.getLogger(__name__)


def get_filter_days_left(smarty: Smarty) -> datetime | None:
    """Return the date when the filter needs to be replaced."""
    if (days_left := smarty.filter_timer) is not None:
        return dt_util.now() + timedelta(days=days_left)
    return None


@dataclass(frozen=True, kw_only=True)
class SmartySensorDescription(SensorEntityDescription):
    """Class describing Smarty sensor."""

    value_fn: Callable[[Smarty], float | datetime | None]


ENTITIES: tuple[SmartySensorDescription, ...] = (
    SmartySensorDescription(
        key="supply_air_temperature",
        translation_key="supply_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda smarty: smarty.supply_air_temperature,
    ),
    SmartySensorDescription(
        key="extract_air_temperature",
        translation_key="extract_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda smarty: smarty.extract_air_temperature,
    ),
    SmartySensorDescription(
        key="outdoor_air_temperature",
        translation_key="outdoor_air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda smarty: smarty.outdoor_air_temperature,
    ),
    SmartySensorDescription(
        key="supply_fan_speed",
        translation_key="supply_fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda smarty: smarty.supply_fan_speed,
    ),
    SmartySensorDescription(
        key="extract_fan_speed",
        translation_key="extract_fan_speed",
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        value_fn=lambda smarty: smarty.extract_fan_speed,
    ),
    SmartySensorDescription(
        key="filter_days_left",
        translation_key="filter_days_left",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=get_filter_days_left,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Smarty Sensor Platform."""

    coordinator = entry.runtime_data

    async_add_entities(
        SmartySensor(coordinator, description) for description in ENTITIES
    )


class SmartySensor(SmartyEntity, SensorEntity):
    """Representation of a Smarty Sensor."""

    entity_description: SmartySensorDescription

    def __init__(
        self,
        coordinator: SmartyCoordinator,
        entity_description: SmartySensorDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

    @property
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.client)
