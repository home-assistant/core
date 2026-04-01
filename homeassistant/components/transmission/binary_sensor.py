"""Binary sensor platform for Transmission integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import TransmissionConfigEntry, TransmissionDataUpdateCoordinator
from .entity import TransmissionEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TransmissionBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Transmission binary sensor entity."""

    is_on_fn: Callable[[TransmissionDataUpdateCoordinator], bool | None]


BINARY_SENSOR_TYPES: tuple[TransmissionBinarySensorEntityDescription, ...] = (
    TransmissionBinarySensorEntityDescription(
        key="port_forwarding",
        translation_key="port_forwarding",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda coordinator: coordinator.port_forwarding,
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TransmissionConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Transmission binary sensors from a config entry."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        TransmissionBinarySensor(coordinator, description)
        for description in BINARY_SENSOR_TYPES
    )


class TransmissionBinarySensor(TransmissionEntity, BinarySensorEntity):
    """Representation of a Transmission binary sensor."""

    entity_description: TransmissionBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return True if the port is open."""
        return self.entity_description.is_on_fn(self.coordinator)
