"""Sensor platform for Heiman integration."""

import logging
from typing import override

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeimanConfigEntry
from .const import DOMAIN
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Sensor Entity Descriptions
SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="energy",
        translation_key="energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="co_concentration",
        translation_key="co_concentration",
        device_class=SensorDeviceClass.CO,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="signal_strength",
        translation_key="signal_strength",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


SENSOR_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    description.key: description for description in SENSOR_TYPES
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HeimanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = entry.runtime_data

    # Track existing entities to avoid duplicates
    existing_entities: set[str] = set()
    # Track currently sensor-eligible properties so new sensor-capable
    # properties are discovered when eligibility changes.
    last_sensor_candidates: frozenset[tuple[str, str]] | None = None

    def _property_is_sensor_eligible(property_id: str, prop: DeviceProperty) -> bool:
        """Return True if a readable property should have a sensor entity."""
        # Only properties described by SENSOR_TYPES get an entity. Everything
        # the entity needs (device class, unit, state class) comes from the
        # entity description, so nothing is inferred at runtime.
        if SENSOR_DESCRIPTIONS.get(property_id.lower()) is None:
            return False
        if not prop.readable:
            return False
        entity_platform = getattr(prop, "entity", None)
        if entity_platform == "sensor":
            return True
        # Do not auto-create a sensor when the property is explicitly assigned
        # to another entity platform.
        if entity_platform is not None:
            return False
        # Skip values that cannot be represented by sensor native_value.
        return prop.data_type not in {"bool", "array", "object"}

    def _create_sensors_for_devices() -> None:
        """Create sensors for all devices and add new ones."""
        nonlocal last_sensor_candidates
        devices = coordinator.get_all_devices()
        current_sensor_candidates: set[tuple[str, str]] = set()
        new_sensors = []

        for device in devices:
            for property_id, prop in device.properties.items():
                if not _property_is_sensor_eligible(property_id, prop):
                    continue
                current_sensor_candidates.add((device.device_id, property_id))
                unique_id = f"{device.device_id}_{property_id}"
                if unique_id in existing_entities:
                    continue
                new_sensors.append(
                    HeimanSensorEntity(
                        coordinator=coordinator,
                        device=device,
                        property_identifier=property_id,
                    )
                )
                existing_entities.add(unique_id)

        current_sensor_candidates_frozen = frozenset(current_sensor_candidates)
        if current_sensor_candidates_frozen == last_sensor_candidates:
            return
        last_sensor_candidates = current_sensor_candidates_frozen

        if new_sensors:
            async_add_entities(new_sensors)

    # Initial setup
    _create_sensors_for_devices()

    # Listen for coordinator updates so newly eligible sensor properties are
    # discovered dynamically. Uses structure hash to avoid creating duplicate
    # entities when no new sensor candidates are found.
    entry.async_on_unload(coordinator.async_add_listener(_create_sensors_for_devices))


class HeimanSensorEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], SensorEntity):
    """Representation of a Heiman sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
        property_identifier: str,
    ) -> None:
        """Initialize the sensor.

        Args:
            coordinator: Data coordinator
            device: Heiman device
            property_identifier: Property identifier
        """
        super().__init__(coordinator)
        self._device = device
        self._property_identifier = property_identifier

        # Generate unique ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}"

        # Get property object
        prop = device.properties.get(property_identifier)

        # Get device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer=device.manufacturer,
            model=device.model or device.product_id,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )

        description = SENSOR_DESCRIPTIONS.get(property_identifier.lower())
        if prop is None or description is None:
            return

        self._attr_device_class = description.device_class
        self._attr_native_unit_of_measurement = (
            description.native_unit_of_measurement
        )
        self._attr_state_class = description.state_class

    @property
    @override
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        device = self.coordinator.data.devices.get(self._device.device_id)
        return device is not None and device.online is True

    @property
    @override
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None

        prop = device.properties.get(self._property_identifier)
        if not prop:
            return None

        return DeviceProperty.validate_sensor_value(prop.value)
