"""Sensor platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import DeviceProperty, HeimanDevice
from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

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
            # Apply icon
            self._apply_icon(property_identifier, prop)

    def _apply_sensor_config(
        self, property_identifier: str, prop: DeviceProperty | None
    ) -> None:
        """Apply sensor configuration based on property type.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # Map common properties to standard device classes
        property_mapping = {
            "temperature": {
                "device_class": SensorDeviceClass.TEMPERATURE,
                "key": "temperature",
            },
            "humidity": {"device_class": SensorDeviceClass.HUMIDITY, "key": "humidity"},
            "battery": {"device_class": SensorDeviceClass.BATTERY, "key": "battery"},
            "voltage": {"device_class": SensorDeviceClass.VOLTAGE, "key": "voltage"},
            "power": {"device_class": SensorDeviceClass.POWER, "key": "power"},
            "energy": {"device_class": SensorDeviceClass.ENERGY, "key": "energy"},
            "co_concentration": {
                "device_class": SensorDeviceClass.CO,
                "key": "co_concentration",
            },
            "signal_strength": {
                "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
                "key": "signal_strength",
            },
            "rssi": {
                "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
                "key": "signal_strength",
            },
            "signal": {
                "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
                "key": "signal_strength",
            },
            "linkquality": {
                "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
                "key": "signal_strength",
            },
            "lqi": {
                "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
                "key": "signal_strength",
            },
        }

        # Try to match known properties
        config = None
        matched_key = None
        for key, cfg in property_mapping.items():
            if key in property_identifier.lower():
                # Find matching SensorEntityDescription from SENSOR_TYPES
                # so this entity can copy supported sensor attributes such as
                # device class, native unit of measurement, and state class
                for desc in SENSOR_TYPES:
                    if desc.key == cfg["key"]:
                        config = desc
                        matched_key = cfg["key"]
                        break
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

    def _apply_icon(
        self, property_identifier: str, prop: DeviceProperty | None
    ) -> None:
        """Apply icon based on device class.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # Set default icon based on device class
        device_class = getattr(self, "_attr_device_class", None)
        if device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_icon = "mdi:thermometer"
        elif device_class == SensorDeviceClass.HUMIDITY:
            self._attr_icon = "mdi:water-percent"
        elif device_class == SensorDeviceClass.BATTERY:
            self._attr_icon = "mdi:battery"
        elif device_class == SensorDeviceClass.SIGNAL_STRENGTH:
            self._attr_icon = "mdi:signal"
        elif device_class == SensorDeviceClass.VOLTAGE:
            self._attr_icon = "mdi:flash-triangle"
        elif device_class == SensorDeviceClass.POWER:
            self._attr_icon = "mdi:flash"
        elif device_class == SensorDeviceClass.ENERGY:
            self._attr_icon = "mdi:lightning-bolt"
        else:
            self._attr_icon = "mdi:gauge"

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

        value = prop.value

        # Handle non-scalar property values (e.g., list/dict)
        # SensorEntity.native_value only supports scalar types
        if value is None:
            return None

        # Boolean values are not valid native sensor states.
        # Return None so numeric device classes do not bypass validation
        # with a non-numeric string state; boolean properties should be
        # exposed by the binary_sensor platform instead.
        if isinstance(value, bool):
            return None

        if not isinstance(value, (str, int, float)):
            _LOGGER.warning(
                "Sensor %s returned unsupported native value: %s (%s). "
                "Returning None to avoid Home Assistant validation error",
                self.name,
                value,
                type(value).__name__,
            )
            return None

        device_class = getattr(self, "_attr_device_class", None)

        # Validate value type matches device class expectations
        # For numeric device classes, ensure value is actually numeric
        if device_class in (
            SensorDeviceClass.SIGNAL_STRENGTH,
            SensorDeviceClass.TEMPERATURE,
            SensorDeviceClass.HUMIDITY,
            SensorDeviceClass.BATTERY,
            SensorDeviceClass.VOLTAGE,
            SensorDeviceClass.POWER,
            SensorDeviceClass.ENERGY,
        ):
            # Reject booleans explicitly because bool is a subclass of int.
            # If value is not a real numeric type, return None to avoid
            # validation errors.
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, (int, float))
            ):
                _LOGGER.warning(
                    "Sensor %s has device class %s but value is non-numeric: %s (%s). "
                    "Returning None to avoid Home Assistant validation error",
                    self.name,
                    device_class,
                    value,
                    type(value).__name__,
                )
                return None

        return value

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
