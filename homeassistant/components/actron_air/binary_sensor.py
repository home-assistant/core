"""Binary sensor platform for Actron Air integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from actron_neo_api import ActronAirStatus

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ActronAirConfigEntry, ActronAirSystemCoordinator
from .entity import ActronAirAcEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class ActronAirBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes Actron Air binary sensor entity."""

    value_fn: Callable[[ActronAirStatus], bool]


BINARY_SENSORS: tuple[ActronAirBinarySensorEntityDescription, ...] = (
    ActronAirBinarySensorEntityDescription(
        key="clean_filter",
        translation_key="clean_filter",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.clean_filter,
    ),
    ActronAirBinarySensorEntityDescription(
        key="defrost_mode",
        translation_key="defrost_mode",
        device_class=BinarySensorDeviceClass.RUNNING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.defrost_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ActronAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Actron Air binary sensor entities."""
    system_coordinators = entry.runtime_data.system_coordinators

    async_add_entities(
        ActronAirBinarySensor(coordinator, description)
        for coordinator in system_coordinators.values()
        for description in BINARY_SENSORS
    )


class ActronAirBinarySensor(ActronAirAcEntity, BinarySensorEntity):
    """Representation of an Actron Air binary sensor."""

    entity_description: ActronAirBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ActronAirSystemCoordinator,
        description: ActronAirBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.serial_number}_{description.key}"

    @property
    @override
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self.coordinator.data)
