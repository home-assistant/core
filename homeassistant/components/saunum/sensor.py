"""Sensor platform for Saunum Leil Sauna Control Unit integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pysaunum import SaunumData

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LeilSaunaConfigEntry
from .entity import LeilSaunaEntity

if TYPE_CHECKING:
    from .coordinator import LeilSaunaCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class LeilSaunaSensorEntityDescription(SensorEntityDescription):
    """Describes Leil Sauna sensor entity."""

    value_fn: Callable[[SaunumData], float | int | None]


SENSORS: tuple[LeilSaunaSensorEntityDescription, ...] = (
    LeilSaunaSensorEntityDescription(
        key="current_temperature",
        translation_key="current_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.current_temperature,
    ),
    LeilSaunaSensorEntityDescription(
        key="heater_elements_active",
        translation_key="heater_elements_active",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.heater_elements_active,
    ),
    LeilSaunaSensorEntityDescription(
        key="on_time",
        translation_key="on_time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.on_time,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeilSaunaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Saunum Leil Sauna sensors from a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(
        LeilSaunaSensorEntity(coordinator, description)
        for description in SENSORS
        if description.value_fn(coordinator.data) is not None
    )


class LeilSaunaSensorEntity(LeilSaunaEntity, SensorEntity):
    """Representation of a Saunum Leil Sauna sensor."""

    entity_description: LeilSaunaSensorEntityDescription

    def __init__(
        self,
        coordinator: LeilSaunaCoordinator,
        description: LeilSaunaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
