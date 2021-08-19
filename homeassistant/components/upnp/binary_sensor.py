"""Support for UPnP/IGD Binary Sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UpnpDataUpdateCoordinator, UpnpEntity
from .const import BINARYSENSOR_ENTITY_DESCRIPTIONS, DOMAIN, LOGGER


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
            sensor_entity=sensor_entity,
        )
        for sensor_entity in BINARYSENSOR_ENTITY_DESCRIPTIONS
    )


class UpnpStatusBinarySensor(UpnpEntity, BinarySensorEntity):
    """Class for UPnP/IGD binary sensors."""

    _attr_device_class = DEVICE_CLASS_CONNECTIVITY

    def __init__(
        self,
        coordinator: UpnpDataUpdateCoordinator,
        sensor_entity: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator=coordinator, sensor_entity=sensor_entity)

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data[self._key] == "Connected"
