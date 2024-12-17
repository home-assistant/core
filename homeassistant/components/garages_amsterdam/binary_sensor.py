"""Binary Sensor platform for Garages Amsterdam."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from odp_amsterdam import Garage

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GaragesAmsterdamConfigEntry
from .coordinator import GaragesAmsterdamDataUpdateCoordinator
from .entity import GaragesAmsterdamEntity


@dataclass(frozen=True, kw_only=True)
class GaragesAmsterdamBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Class describing Garages Amsterdam binary sensor entity."""

    is_on: Callable[[Garage], bool]


BINARY_SENSORS: tuple[GaragesAmsterdamBinarySensorEntityDescription, ...] = (
    GaragesAmsterdamBinarySensorEntityDescription(
        key="state",
        translation_key="state",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on=lambda garage: garage.state != "ok",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GaragesAmsterdamConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Defer sensor setup to the shared sensor module."""
    coordinator = entry.runtime_data

    async_add_entities(
        GaragesAmsterdamBinarySensor(
            coordinator=coordinator,
            garage_name=entry.data["garage_name"],
            description=description,
        )
        for description in BINARY_SENSORS
    )


class GaragesAmsterdamBinarySensor(GaragesAmsterdamEntity, BinarySensorEntity):
    """Binary Sensor representing garages amsterdam data."""

    entity_description: GaragesAmsterdamBinarySensorEntityDescription

    def __init__(
        self,
        *,
        coordinator: GaragesAmsterdamDataUpdateCoordinator,
        garage_name: str,
        description: GaragesAmsterdamBinarySensorEntityDescription,
    ) -> None:
        """Initialize garages amsterdam binary sensor."""
        super().__init__(coordinator, garage_name)
        self.entity_description = description
        self._attr_unique_id = f"{garage_name}-{description.key}"

    @property
    def is_on(self) -> bool:
        """If the binary sensor is currently on or off."""
        return self.entity_description.is_on(self.coordinator.data[self._garage_name])
