"""Sensor platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import DeviceProperty, HeimanDevice
from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = entry.runtime_data

    # Track existing entities to avoid duplicates
    existing_entities: set[str] = set()

    def _create_sensors_for_devices() -> None:
        """Create sensors for all devices and add new ones."""
        devices = coordinator.get_all_devices()
        new_sensors = []

        for device in devices:
            # Create sensor for each readable property of each device
            for property_id, prop in device.properties.items():
                if not prop.readable:
                    continue

                # Use entity field from DeviceProperty
                if hasattr(prop, "entity") and prop.entity == "sensor":
                    unique_id = f"{device.device_id}_{property_id}_sensor"
                    if unique_id not in existing_entities:
                        new_sensors.append(
                            HeimanSensorEntity(
                                coordinator=coordinator,
                                device=device,
                                property_identifier=property_id,
                            )
                        )
                        existing_entities.add(unique_id)
                # Create sensors for readable properties unless they are
                # explicitly assigned to a different entity platform.
                elif hasattr(prop, "entity") and prop.entity not in (None, "sensor"):
                    continue
                else:
                    # Skip non-scalar and boolean-valued properties when
                    # auto-creating sensors (unless explicitly marked as
                    # entity='sensor'), because native_value returns None for
                    # unsupported complex values and this creates
                    # permanently-unknown, unusable sensor entities.
                    # Check both data_type metadata and actual value type
                    if prop.data_type in {
                        "bool",
                        "array",
                        "object",
                    } or isinstance(prop.value, (bool, list, dict)):
                        continue
                    unique_id = f"{device.device_id}_{property_id}_sensor"
                    if unique_id not in existing_entities:
                        new_sensors.append(
                            HeimanSensorEntity(
                                coordinator=coordinator,
                                device=device,
                                property_identifier=property_id,
                            )
                        )
                        existing_entities.add(unique_id)

        if new_sensors:
            async_add_entities(new_sensors)

    # Initial setup
    _create_sensors_for_devices()

    # Listen for coordinator updates to add new devices dynamically
    # Only trigger discovery when coordinator data changes (new devices/properties)
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
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_sensor"

        # Get property object
        prop = device.properties.get(property_identifier)

        # Set name
        self._attr_name = prop.name if prop else property_identifier

        # Get device info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer=device.manufacturer,
            model=device.model or device.product_id,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )

        # Apply device class and unit based on property type (only if property exists)
        if prop:
            self._apply_sensor_config(property_identifier, prop)

    def _apply_sensor_config(
        self, property_identifier: str, prop: DeviceProperty | None
    ) -> None:
        """Apply sensor configuration based on property type.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # Map property name aliases to SENSOR_TYPES keys
        # This handles variations like RSSI, Signal, LinkQuality -> signal_strength
        property_aliases = {
            "rssi": "signal_strength",
            "signal": "signal_strength",
            "linkquality": "signal_strength",
            "lqi": "signal_strength",
        }

        # Find matching SensorEntityDescription from SENSOR_TYPES
        config = None
        matched_key = None

        # First check if property has an alias
        normalized_prop = property_identifier.lower()
        sensor_key = property_aliases.get(normalized_prop, normalized_prop)

        for desc in SENSOR_TYPES:
            if desc.key in sensor_key or sensor_key in desc.key:
                config = desc
                matched_key = desc.key
                break

        if config and prop:
            # For signal_strength properties, verify the value is numeric
            # Some devices may have "SignalStrength" property with string values
            if matched_key == "signal_strength":
                numeric_data_types = [
                    "int",
                    "double",
                    "float",
                    "long",
                    "short",
                    "byte",
                    "number",
                ]
                # Exclude string/enum types
                non_numeric_data_types = [
                    "string",
                    "text",
                    "enum",
                    "bool",
                ]
                # Check if value is numeric
                value_is_numeric = (
                    prop.value is not None
                    and isinstance(prop.value, (int, float))
                    and not isinstance(prop.value, bool)
                )
                # Check if data_type indicates numeric
                data_type_is_numeric = (
                    prop.data_type is not None
                    and prop.data_type in numeric_data_types
                    and prop.data_type not in non_numeric_data_types
                )
                if not (value_is_numeric or data_type_is_numeric):
                    # Skip applying signal_strength device class for non-numeric values
                    matched_key = None
                    config = None

        if config and matched_key:
            if config.device_class:
                self._attr_device_class = config.device_class
            self._attr_native_unit_of_measurement = config.native_unit_of_measurement
            if config.state_class:
                self._attr_state_class = config.state_class
        elif prop:
            # Only set state_class when the current value is numeric.
            # Note: bool is a subclass of int, so we explicitly exclude it.
            if (
                prop.value is not None
                and isinstance(prop.value, (int, float))
                and not isinstance(prop.value, bool)
            ):
                self._attr_state_class = SensorStateClass.MEASUREMENT
            # Non-numeric sensors should not have state_class set

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return False

        return device.online is True

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state of the sensor."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None

        prop = device.properties.get(self._property_identifier)
        if not prop:
            return None

        return prop.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attributes = {}

        device = self.coordinator.get_device(self._device.device_id)
        if device:
            prop = device.properties.get(self._property_identifier)
            if prop:
                if prop.unit:
                    attributes["unit"] = prop.unit
                if prop.data_type:
                    attributes["data_type"] = prop.data_type

        return attributes
