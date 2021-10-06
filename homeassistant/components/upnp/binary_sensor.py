"""Support for UPnP/IGD Binary Sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpBinarySensorEntityDescription, UpnpDataUpdateCoordinator, UpnpEntity
from .const import DOMAIN, LOGGER, WAN_STATUS

BINARYSENSOR_ENTITY_DESCRIPTIONS: tuple[UpnpBinarySensorEntityDescription, ...] = (
    UpnpBinarySensorEntityDescription(
        key=WAN_STATUS,
        name="wan status",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the UPnP/IGD sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    LOGGER.debug("Adding binary sensor")

    async_add_entities(
        UpnpStatusBinarySensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in BINARYSENSOR_ENTITY_DESCRIPTIONS
        if coordinator.data.get(entity_description.key) is not None
    )


class UpnpStatusBinarySensor(UpnpEntity, BinarySensorEntity):
    """Class for UPnP/IGD binary sensors."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

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
