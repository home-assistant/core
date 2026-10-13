"""Support for Verisure sensors."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GIID, DEVICE_TYPE_NAME, DOMAIN
from .coordinator import VerisureConfigEntry, VerisureDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VerisureConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Verisure sensors based on a config entry."""
    coordinator = entry.runtime_data

    sensors: list[Entity] = [
        VerisureThermometer(coordinator, serial_number)
        for serial_number, values in coordinator.data["climate"].items()
        if "temperatureValue" in values
    ]

    sensors.extend(
        VerisureHygrometer(coordinator, serial_number)
        for serial_number, values in coordinator.data["climate"].items()
        if values.get("humidityEnabled")
    )

    async_add_entities(sensors)


class VerisureThermometer(
    CoordinatorEntity[VerisureDataUpdateCoordinator], SensorEntity
):
    """Representation of a Verisure thermometer."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_temperature"
        self.serial_number = serial_number
        device = coordinator.data["climate"][serial_number]["device"]
        device_type = device["gui"]["label"]
        self._attr_device_info = DeviceInfo(
            name=device["area"],
            manufacturer="Verisure",
            model=DEVICE_TYPE_NAME.get(device_type, device_type),
            identifiers={(DOMAIN, serial_number)},
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, coordinator.config_entry.data[CONF_GIID]),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
            configuration_url="https://mypages.verisure.com",
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self.coordinator.data["climate"][self.serial_number]["temperatureValue"]

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["climate"]
            and "temperatureValue"
            in self.coordinator.data["climate"][self.serial_number]
        )


class VerisureHygrometer(
    CoordinatorEntity[VerisureDataUpdateCoordinator], SensorEntity
):
    """Representation of a Verisure hygrometer."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: VerisureDataUpdateCoordinator, serial_number: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{serial_number}_humidity"
        self.serial_number = serial_number
        device = coordinator.data["climate"][serial_number]["device"]
        device_type = device["gui"]["label"]
        self._attr_device_info = DeviceInfo(
            name=device["area"],
            manufacturer="Verisure",
            model=DEVICE_TYPE_NAME.get(device_type, device_type),
            identifiers={(DOMAIN, serial_number)},
            via_device_id=dr.async_get_device_id_by_identifier(
                coordinator.hass,
                (DOMAIN, coordinator.config_entry.data[CONF_GIID]),
                config_entry_id=coordinator.config_entry.entry_id,
            ),
            configuration_url="https://mypages.verisure.com",
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return the state of the entity."""
        return self.coordinator.data["climate"][self.serial_number]["humidityValue"]

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.serial_number in self.coordinator.data["climate"]
            and "humidityValue" in self.coordinator.data["climate"][self.serial_number]
        )
