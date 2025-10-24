"""Sensor platform for Saunum Leil Sauna Control Unit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry, LeilSaunaCoordinator
from .entity import LeilSaunaEntity
from .helpers import convert_temperature, get_temperature_unit

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LeilSaunaSensorEntityDescription(SensorEntityDescription):
    """Describes Saunum Leil Sauna sensor entity."""

    value_fn: Callable[[dict[str, Any]], int | float | None]


SENSORS: tuple[LeilSaunaSensorEntityDescription, ...] = (
    LeilSaunaSensorEntityDescription(
        key="current_temperature",
        translation_key="current_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:thermometer",
        value_fn=lambda data: data.get("current_temperature"),
    ),
    LeilSaunaSensorEntityDescription(
        key="on_time",
        translation_key="on_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:progress-clock",
        value_fn=lambda data: data.get("on_time_seconds"),
    ),
    LeilSaunaSensorEntityDescription(
        key="remaining_time",
        translation_key="remaining_time",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        icon="mdi:timer-outline",
        value_fn=lambda data: data.get("remaining_time_minutes"),
    ),
    LeilSaunaSensorEntityDescription(
        key="heater_status",
        translation_key="heater_status",
        icon="mdi:heat-wave",
        value_fn=lambda data: data.get("heater_status"),
    ),
    LeilSaunaSensorEntityDescription(
        key="fan_speed_sensor",
        translation_key="fan_speed_sensor",
        icon="mdi:fan",
        value_fn=lambda data: data.get("fan_speed"),
    ),
    LeilSaunaSensorEntityDescription(
        key="sauna_type_sensor",
        translation_key="sauna_type_sensor",
        icon="mdi:format-list-bulleted-type",
        value_fn=lambda data: data.get("sauna_type"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna sensor entities."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaSensor(coordinator, description) for description in SENSORS
    )


class LeilSaunaSensor(LeilSaunaEntity, SensorEntity):
    """Representation of a Saunum Leil Sauna sensor."""

    entity_description: LeilSaunaSensorEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

        # Set temperature unit for temperature sensors
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            temp_unit = get_temperature_unit(coordinator.hass)
            self._attr_native_unit_of_measurement = temp_unit

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        value = self.entity_description.value_fn(self.coordinator.data)

        # Convert temperature if needed
        if (
            self.entity_description.device_class == SensorDeviceClass.TEMPERATURE
            and value is not None
        ):
            temp_unit = get_temperature_unit(self.hass)
            value = convert_temperature(value, UnitOfTemperature.CELSIUS, temp_unit)

        return value
