"""Support for Verisure binary sensors."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_OPENING,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CONF_DOOR_WINDOW, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[CoordinatorEntity]], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure binary sensors."""
    coordinator = hass.data[DOMAIN]

    sensors: list[CoordinatorEntity] = [VerisureEthernetStatus(coordinator)]

    if int(coordinator.config.get(CONF_DOOR_WINDOW, 1)):
        sensors.extend(
            [
                VerisureDoorWindowSensor(coordinator, serial_number)
                for serial_number in coordinator.data["door_window"]
            ]
        )

    add_entities(sensors)


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
        """Return the name of the binary sensor."""
        return self.coordinator.data["door_window"][self.serial_number]["area"]

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this alarm control panel."""
        return f"{self.serial_number}_door_window"

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
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
        """Return the name of the binary sensor."""
        return "Verisure Ethernet status"

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
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY
