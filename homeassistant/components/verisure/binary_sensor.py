"""Support for Verisure binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, Entity, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DOMAIN
from .coordinator import VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verisure binary sensors based on a config entry."""
    coordinator: VerisureDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[Entity] = [VerisureEthernetStatus(coordinator)]

    sensors.extend(
        VerisureDoorWindowSensor(coordinator, serial_number)
        for serial_number in coordinator.data["door_window"]
    )

    async_add_entities(sensors)


class VerisureDoorWindowSensor(
    CoordinatorEntity[VerisureDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Verisure door window sensor."""

    _attr_device_class = BinarySensorDeviceClass.OPENING
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the Verisure door window sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_door_window"
        self.serial_number = serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["door_window"][self.serial_number]["area"]
        return DeviceInfo(
            name=area,
            suggested_area=area,
            manufacturer="Verisure",
            model="Shock Sensor Detector",
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

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


class VerisureEthernetStatus(
    CoordinatorEntity[VerisureDataUpdateCoordinator], BinarySensorEntity
):
    """Representation of a Verisure VBOX internet status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = "Ethernet status"

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.entry.data[CONF_GIID]}_ethernet"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name="Verisure Alarm",
            manufacturer="Verisure",
            model="VBox",
            identifiers={(DOMAIN, self.coordinator.entry.data[CONF_GIID])},
            configuration_url="https://mypages.verisure.com",
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the sensor."""
        return self.coordinator.data["ethernet"]

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return super().available and self.coordinator.data["ethernet"] is not None
