"""Support for Verisure binary sensors."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable, Mapping

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_OPENING,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[Iterable[Entity]], None],
) -> None:
    """Set up Verisure binary sensors based on a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[Entity] = [
        VerisureEthernetStatus(coordinator),
        VerisureFirmwareUpdate(coordinator),
    ]

    sensors.extend(
        VerisureDoorWindowSensor(coordinator, serial_number)
        for serial_number in coordinator.data["door_window"]
    )

    async_add_entities(sensors)


class VerisureDoorWindowSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Verisure door window sensor."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure door window sensor."""
        super().__init__(coordinator)
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return self.coordinator.data["door_window"][self.serial_number]["area"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.serial_number}_door_window"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        area = self.coordinator.data["door_window"][self.serial_number]["area"]
        return {
            "name": area,
            "suggested_area": area,
            "manufacturer": "Verisure",
            "model": "Shock Sensor Detector",
            "identifiers": {(DOMAIN, self.serial_number)},
            "via_device": (DOMAIN, self.coordinator.entry.data[CONF_GIID]),
        }

    @property
    def device_class(self) -> str:
        """Return the class of this entity."""
        return DEVICE_CLASS_OPENING

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return (
            self.coordinator.data["door_window"][self.serial_number]["state"] == "OPEN"
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["door_window"]
        )


class VerisureEthernetStatus(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Verisure VBOX internet status."""

    coordinator: VerisureDataUpdateCoordinator

    @property
    def name(self) -> str:
        """Return the name of this entity."""
        return "Verisure Ethernet status"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.entry.data[CONF_GIID]}_ethernet"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        return {
            "name": "Verisure Alarm",
            "manufacturer": "Verisure",
            "model": "VBox",
            "identifiers": {(DOMAIN, self.coordinator.entry.data[CONF_GIID])},
            "sw_version": self.coordinator.data["firmware"]["current"],
        }

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data["ethernet"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data["ethernet"] is not None

    @property
    def device_class(self) -> str:
        """Return the class of this entity."""
        return DEVICE_CLASS_CONNECTIVITY


class VerisureFirmwareUpdate(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Verisure firmware."""

    coordinator: VerisureDataUpdateCoordinator

    @property
    def name(self) -> str:
        """Return the name of the binary sensor."""
        return "Verisure Firmware update"

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data["firmware"]["upgradeable"]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information about this entity."""
        return {
            "name": "Verisure Alarm",
            "manufacturer": "Verisure",
            "model": "VBox",
            "identifiers": {(DOMAIN, self.coordinator.entry.data[CONF_GIID])},
            "sw_version": self.coordinator.data["firmware"]["current"],
        }

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes."""
        return {
            "current": self.coordinator.data["firmware"]["current"],
            "latest": self.coordinator.data["firmware"]["latest"],
        }

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.entry.data[CONF_GIID]}_firmware"

    @property
    def entity_registry_enabled_default(self):
        """Return if the entity should be enabled when first added."""
        return False
