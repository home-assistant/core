"""Support for monitoring Dremel 3D Printer binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Dremel3DPrinterDataUpdateCoordinator, Dremel3DPrinterDeviceEntity
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the available Dremel binary sensors."""
    coordinator: Dremel3DPrinterDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    device_id = config_entry.unique_id

    assert device_id is not None

    entities: list[BinarySensorEntity] = [
        Dremel3DPrinterDoorBinarySensor(coordinator, config_entry),
        Dremel3DPrinterMainBinarySensor(coordinator, config_entry),
    ]

    async_add_entities(entities)


class Dremel3DPrinterDoorBinarySensor(Dremel3DPrinterDeviceEntity, BinarySensorEntity):
    """Representation of a Dremel 3D Printer door binary sensor."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer binary sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = "Door Contact"
        self._attr_unique_id = f"door-contact-{config_entry.unique_id}"

    @property
    def is_on(self) -> bool:
        """Return true if door is open."""
        return bool(self.coordinator.api.is_door_open())

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor."""
        return BinarySensorDeviceClass.DOOR


class Dremel3DPrinterMainBinarySensor(Dremel3DPrinterDeviceEntity, BinarySensorEntity):
    """Representation of the current status of the printer as a binary sensor."""

    def __init__(
        self,
        coordinator: Dremel3DPrinterDataUpdateCoordinator,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize a new Dremel 3D Printer binary sensor."""
        super().__init__(coordinator, config_entry)
        self._attr_name = config_entry.title
        self._attr_unique_id = f"main-sensor-{config_entry.unique_id}"
        self._attr_extra_state_attributes = self.coordinator.api.get_printer_info()

    @property
    def is_on(self) -> bool:
        """Return true if it's currently printing."""
        return bool(self.coordinator.api.is_running())

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor."""
        return BinarySensorDeviceClass.RUNNING
