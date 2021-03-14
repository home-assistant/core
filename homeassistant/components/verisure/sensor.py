"""Support for Verisure sensors."""
from __future__ import annotations

from typing import Any, Callable

from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HYDROMETERS, CONF_MOUSE, CONF_THERMOMETERS, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


def setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    add_entities: Callable[[list[CoordinatorEntity], bool], None],
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up the Verisure platform."""
    coordinator = hass.data[DOMAIN]

    sensors: list[CoordinatorEntity] = []
    if int(coordinator.config.get(CONF_THERMOMETERS, 1)):
        sensors.extend(
            [
                VerisureThermometer(coordinator, serial_number)
                for serial_number, values in coordinator.data["climate"].items()
                if "temperature" in values
            ]
        )

    if int(coordinator.config.get(CONF_HYDROMETERS, 1)):
        sensors.extend(
            [
                VerisureHygrometer(coordinator, serial_number)
                for serial_number, values in coordinator.data["climate"].items()
                if "humidity" in values
            ]
        )

    if int(coordinator.config.get(CONF_MOUSE, 1)):
        sensors.extend(
            [
                VerisureMouseDetection(coordinator, serial_number)
                for serial_number in coordinator.data["mice"]
            ]
        )

    add_entities(sensors)


class VerisureThermometer(CoordinatorEntity, Entity):
    """Representation of a Verisure thermometer."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        name = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return f"{name} Temperature"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.serial_number}_temperature"

    @property
    def state(self) -> str | None:
        """Return the state of the entity."""
        return self.coordinator.data["climate"][self.serial_number]["temperature"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["climate"]
            and "temperature" in self.coordinator.data["climate"][self.serial_number]
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return TEMP_CELSIUS


class VerisureHygrometer(CoordinatorEntity, Entity):
    """Representation of a Verisure hygrometer."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        name = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return f"{name} Humidity"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.serial_number}_humidity"

    @property
    def state(self) -> str | None:
        """Return the state of the entity."""
        return self.coordinator.data["climate"][self.serial_number]["humidity"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["climate"]
            and "humidity" in self.coordinator.data["climate"][self.serial_number]
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return PERCENTAGE


class VerisureMouseDetection(CoordinatorEntity, Entity):
    """Representation of a Verisure mouse detector."""

    coordinator: VerisureDataUpdateCoordinator

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        name = self.coordinator.data["mice"][self.serial_number]["area"]
        return f"{name} Mouse"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.serial_number}_mice"

    @property
    def state(self) -> str | None:
        """Return the state of the device."""
        return self.coordinator.data["mice"][self.serial_number]["detections"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["mice"]
            and "detections" in self.coordinator.data["mice"][self.serial_number]
        )

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity."""
        return "Mice"
