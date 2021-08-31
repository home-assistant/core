"""Support for Verisure sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DEVICE_TYPE_NAME, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure sensors based on a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[Entity] = [
        VerisureThermometer(coordinator, serial_number)
        for serial_number, values in coordinator.data["climate"].items()
        if "temperature" in values
    ]

    sensors.extend(
        VerisureHygrometer(coordinator, serial_number)
        for serial_number, values in coordinator.data["climate"].items()
        if "humidity" in values
    )

    sensors.extend(
        VerisureMouseDetection(coordinator, serial_number)
        for serial_number in coordinator.data["mice"]
    )

    async_add_entities(sensors)


class VerisureThermometer(CoordinatorEntity, SensorEntity):
    """Representation of a Verisure thermometer."""

    coordinator: VerisureDataUpdateCoordinator

    _attr_device_class = DEVICE_CLASS_TEMPERATURE
    _attr_native_unit_of_measurement = TEMP_CELSIUS

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_temperature"
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        name = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return f"{name} Temperature"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        device_type = self.coordinator.data["climate"][self.serial_number].get(
            "deviceType"
        )
        area = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return {
            "name": area,
            "suggested_area": area,
            "manufacturer": "Verisure",
            "model": DEVICE_TYPE_NAME.get(device_type, device_type),
            "identifiers": {(DOMAIN, self.serial_number)},
            "via_device": (DOMAIN, self.coordinator.entry.data[CONF_GIID]),
        }

    @property
    def native_value(self) -> str | None:
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


class VerisureHygrometer(CoordinatorEntity, SensorEntity):
    """Representation of a Verisure hygrometer."""

    coordinator: VerisureDataUpdateCoordinator

    _attr_device_class = DEVICE_CLASS_HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_humidity"
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        name = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return f"{name} Humidity"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        device_type = self.coordinator.data["climate"][self.serial_number].get(
            "deviceType"
        )
        area = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return {
            "name": area,
            "suggested_area": area,
            "manufacturer": "Verisure",
            "model": DEVICE_TYPE_NAME.get(device_type, device_type),
            "identifiers": {(DOMAIN, self.serial_number)},
            "via_device": (DOMAIN, self.coordinator.entry.data[CONF_GIID]),
        }

    @property
    def native_value(self) -> str | None:
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


class VerisureMouseDetection(CoordinatorEntity, SensorEntity):
    """Representation of a Verisure mouse detector."""

    coordinator: VerisureDataUpdateCoordinator

    _attr_native_unit_of_measurement = "Mice"

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_mice"
        self.serial_number = serial_number

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        name = self.coordinator.data["mice"][self.serial_number]["area"]
        return f"{name} Mouse"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["mice"][self.serial_number]["area"]
        return {
            "name": area,
            "suggested_area": area,
            "manufacturer": "Verisure",
            "model": "Mouse detector",
            "identifiers": {(DOMAIN, self.serial_number)},
            "via_device": (DOMAIN, self.coordinator.entry.data[CONF_GIID]),
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self.coordinator.data["mice"][self.serial_number]["detections"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["mice"]
            and "detections" in self.coordinator.data["mice"][self.serial_number]
        )
