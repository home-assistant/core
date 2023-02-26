"""Support for Verisure sensors."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
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


class VerisureThermometer(
    CoordinatorEntity[VerisureDataUpdateCoordinator], SensorEntity
):
    """Representation of a Verisure thermometer."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_name = "Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_temperature"
        self.serial_number = serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        device_type = self.coordinator.data["climate"][self.serial_number].get(
            "deviceType"
        )
        area = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return DeviceInfo(
            name=area,
            suggested_area=area,
            manufacturer="Verisure",
            model=DEVICE_TYPE_NAME.get(device_type, device_type),
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

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


class VerisureHygrometer(
    CoordinatorEntity[VerisureDataUpdateCoordinator], SensorEntity
):
    """Representation of a Verisure hygrometer."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_has_entity_name = True
    _attr_name = "Humidity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_humidity"
        self.serial_number = serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        device_type = self.coordinator.data["climate"][self.serial_number].get(
            "deviceType"
        )
        area = self.coordinator.data["climate"][self.serial_number]["deviceArea"]
        return DeviceInfo(
            name=area,
            suggested_area=area,
            manufacturer="Verisure",
            model=DEVICE_TYPE_NAME.get(device_type, device_type),
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

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


class VerisureMouseDetection(
    CoordinatorEntity[VerisureDataUpdateCoordinator], SensorEntity
):
    """Representation of a Verisure mouse detector."""

    _attr_name = "Mouse"
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "Mice"

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_mice"
        self.serial_number = serial_number

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        area = self.coordinator.data["mice"][self.serial_number]["area"]
        return DeviceInfo(
            name=area,
            suggested_area=area,
            manufacturer="Verisure",
            model="Mouse detector",
            identifiers={(DOMAIN, self.serial_number)},
            via_device=(DOMAIN, self.coordinator.entry.data[CONF_GIID]),
            configuration_url="https://mypages.verisure.com",
        )

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
