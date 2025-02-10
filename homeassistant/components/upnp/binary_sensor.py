"""Support for UPnP/IGD Binary Sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER, WAN_STATUS
from .coordinator import UpnpConfigEntry, UpnpDataUpdateCoordinator
from .entity import UpnpEntity, UpnpEntityDescription


@dataclass(frozen=True)
class UpnpBinarySensorEntityDescription(
    UpnpEntityDescription, BinarySensorEntityDescription
):
    """A class that describes binary sensor UPnP entities."""


SENSOR_DESCRIPTIONS: tuple[UpnpBinarySensorEntityDescription, ...] = (
    UpnpBinarySensorEntityDescription(
        key=WAN_STATUS,
        translation_key="wan_status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UpnpConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    coordinator = config_entry.runtime_data

    entities = [
        UpnpStatusBinarySensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in SENSOR_DESCRIPTIONS
        if coordinator.data.get(entity_description.key) is not None
    ]
    async_add_entities(entities)
    LOGGER.debug("Added binary_sensor entities: %s", entities)


class UpnpStatusBinarySensor(UpnpEntity, BinarySensorEntity):
    """Class for UPnP/IGD binary sensors."""

    entity_description: UpnpBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        entity_description: UpnpBinarySensorEntityDescription,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator=coordinator, entity_description=entity_description)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data[self.entity_description.key] == "Connected"

    async def async_added_to_hass(self) -> None:
        """Subscribe to updates."""
        await super().async_added_to_hass()

        # Register self at coordinator.
        key = self.entity_description.key
        entity_id = self.entity_id
        unregister = self.coordinator.register_entity(key, entity_id)
        self.async_on_remove(unregister)
