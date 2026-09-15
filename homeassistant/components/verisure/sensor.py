"""Support for Verisure sensors."""

from typing import override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
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

    sensors.append(VerisureArmStatus(coordinator))

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


class VerisureArmStatus(CoordinatorEntity[VerisureDataUpdateCoordinator], SensorEntity):
    """Whether Verisure currently requires force to arm.

    Backed by an arm-state dry run, run when a door/window state changes or
    otherwise at least once per DRY_RUN_FALLBACK_INTERVAL.
    """

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_options = ["ready", "bypass_needed"]
    _attr_translation_key = "arm_status"

    @property
    @override
    def unique_id(self) -> str:
        """Return the unique ID for this entity."""
        return f"{self.coordinator.config_entry.data[CONF_GIID]}_arm_status"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device information about this entity."""
        return DeviceInfo(
            name="Verisure Alarm",
            manufacturer="Verisure",
            model="VBox",
            identifiers={(DOMAIN, self.coordinator.config_entry.data[CONF_GIID])},
            configuration_url="https://mypages.verisure.com",
        )

    @property
    @override
    def native_value(self) -> str | None:
        """Return whether arming currently requires force."""
        force_arm_required = self.coordinator.data["force_arm_required"]
        if force_arm_required is None:
            return None
        return "bypass_needed" if force_arm_required else "ready"
