"""Sensor platform for Garages Amsterdam."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from odp_amsterdam import Garage

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import (
    GaragesAmsterdamConfigEntry,
    GaragesAmsterdamDataUpdateCoordinator,
)
from .entity import GaragesAmsterdamEntity


@dataclass(frozen=True, kw_only=True)
class GaragesAmsterdamSensorEntityDescription(SensorEntityDescription):
    """Class describing Garages Amsterdam sensor entity."""

    value_fn: Callable[[Garage], StateType]


SENSORS: tuple[GaragesAmsterdamSensorEntityDescription, ...] = (
    GaragesAmsterdamSensorEntityDescription(
        key="free_space_short",
        translation_key="free_space_short",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda garage: garage.free_space_short,
    ),
    GaragesAmsterdamSensorEntityDescription(
        key="free_space_long",
        translation_key="free_space_long",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda garage: garage.free_space_long,
    ),
    GaragesAmsterdamSensorEntityDescription(
        key="short_capacity",
        translation_key="short_capacity",
        value_fn=lambda garage: garage.short_capacity,
    ),
    GaragesAmsterdamSensorEntityDescription(
        key="long_capacity",
        translation_key="long_capacity",
        value_fn=lambda garage: garage.long_capacity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GaragesAmsterdamConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = entry.runtime_data

    async_add_entities(
        GaragesAmsterdamSensor(
            coordinator=coordinator,
            garage_name=entry.data["garage_name"],
            description=description,
        )
        for description in SENSORS
        if description.value_fn(coordinator.data[entry.data["garage_name"]]) is not None
    )


class GaragesAmsterdamSensor(GaragesAmsterdamEntity, SensorEntity):
    """Sensor representing garages amsterdam data."""

    entity_description: GaragesAmsterdamSensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: GaragesAmsterdamDataUpdateCoordinator,
        garage_name: str,
        description: GaragesAmsterdamSensorEntityDescription,
    ) -> None:
        """Initialize garages amsterdam sensor."""
        super().__init__(coordinator, garage_name)
        self.entity_description = description
        self._attr_unique_id = f"{garage_name}-{description.key}"

    @property
    def available(self) -> bool:
        """Return if sensor is available."""
        return self.coordinator.last_update_success and (
            self._garage_name in self.coordinator.data
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data[self._garage_name]
        )
