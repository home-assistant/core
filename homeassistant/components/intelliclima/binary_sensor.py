"""Support for IntelliClima Binary Sensors."""

from collections.abc import Callable
from dataclasses import dataclass

from pyintelliclima.intelliclima_types import IntelliClimaECO

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator
from .entity import IntelliClimaECOEntity


@dataclass(frozen=True)
class IntelliClimaBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[IntelliClimaECO], bool | None]


@dataclass(frozen=True)
class IntelliClimaBinarySensorEntityDescription(
    BinarySensorEntityDescription, IntelliClimaBinarySensorRequiredKeysMixin
):
    """Describes a binary sensor entity."""


INTELLICLIMA_BINARY_SENSORS: tuple[IntelliClimaBinarySensorEntityDescription, ...] = (
    IntelliClimaBinarySensorEntityDescription(
        key="master_satellite",
        translation_key="master_satellite",
        value_fn=lambda device_data: device_data.role == "1",
    ),
    IntelliClimaBinarySensorEntityDescription(
        key="winter_summer",
        translation_key="winter_summer",
        value_fn=lambda device_data: device_data.ws == "0",
    ),
    IntelliClimaBinarySensorEntityDescription(
        key="filter_cleaning",
        translation_key="filter_cleaning",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device_data: device_data.sanification is not None,
        device_class=BinarySensorDeviceClass.PROBLEM,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a IntelliClima On/Off Sensor."""
    coordinator: IntelliClimaCoordinator = entry.runtime_data

    entities: list[IntelliClimaBinarySensor] = []
    for ecocomfort2 in coordinator.data.ecocomfort2_devices.values():
        entities.extend(
            IntelliClimaBinarySensor(
                coordinator=coordinator, device=ecocomfort2, description=description
            )
            for description in INTELLICLIMA_BINARY_SENSORS
        )

    async_add_entities(entities)


class IntelliClimaBinarySensor(IntelliClimaECOEntity, BinarySensorEntity):
    """Extends IntelliClimaEntity with Binary Sensor specific logic."""

    entity_description: IntelliClimaBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Use this to get the correct value."""
        return self.entity_description.value_fn(self._device_data)
