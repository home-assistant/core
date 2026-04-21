"""Binary sensor platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_DEVICE_CLASS_MAP, DOMAIN, ENTITY_ICONS
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman binary sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Track existing entities to avoid duplicates
    existing_entities: set[str] = set()

    def _create_binary_sensors_for_devices() -> None:
        """Create binary sensors for all devices and add new ones."""
        devices = coordinator.get_all_devices()
        new_binary_sensors = []

        for device in devices:
            for property_id, prop in device.properties.items():
                if not prop.readable:
                    continue

                # Use entity field from DeviceProperty
                if hasattr(prop, "entity") and prop.entity == "binary_sensor":
                    unique_id = f"{device.device_id}_{property_id}_binary_sensor"
                    if unique_id not in existing_entities:
                        new_binary_sensors.append(
                            HeimanBinarySensorEntity(
                                coordinator=coordinator,
                                device=device,
                                property_identifier=property_id,
                            )
                        )
                        existing_entities.add(unique_id)

        if new_binary_sensors:
            async_add_entities(new_binary_sensors)

    # Initial setup
    _create_binary_sensors_for_devices()

    # Listen for coordinator updates to add new devices dynamically
    entry.async_on_unload(coordinator.async_add_listener(_create_binary_sensors_for_devices))

class HeimanBinarySensorEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], BinarySensorEntity):
    """Representation of a Heiman binary sensor entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
        property_identifier: str,
    ) -> None:
        """Initialize the binary sensor.

        Args:
            coordinator: Data coordinator
            device: Heiman device
            property_identifier: Property identifier
        """
        super().__init__(coordinator)
        self._device = device
        self._property_identifier = property_identifier

        # Generate unique ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_binary_sensor"

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

        # Apply device class and icon based on property type
        if prop:
            self._apply_device_class(property_identifier, prop)
            # Apply icon
            self._apply_icon(property_identifier, prop)
    
    def _apply_device_class(
        self, property_identifier: str, prop: DeviceProperty | None
    ) -> None:
        """Apply device class based on property type.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        prop_lower = property_identifier.lower()
        # Try to match known binary sensor types
        for key, device_class in BINARY_SENSOR_DEVICE_CLASS_MAP.items():
            if key in prop_lower:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
                return

        # Default to generic type for alarm-related properties
        if "alarm" in prop_lower:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
    
    def _apply_icon(
        self, property_identifier: str, prop: DeviceProperty | None
    ) -> None:
        """Apply icon based on property type.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # First try to get from ENTITY_ICONS (using original case)
        icons_config = ENTITY_ICONS.get("binary_sensor", {})

        if property_identifier in icons_config:
            self._attr_icon = icons_config[property_identifier]
            return

        # If not found, try lowercase matching
        prop_lower = property_identifier.lower()
        if prop_lower in icons_config:
            self._attr_icon = icons_config[prop_lower]
            return

        # Set default icon based on device class (use getattr for safe access)
        device_class = getattr(self, "_attr_device_class", None)
        if device_class == BinarySensorDeviceClass.SMOKE:
            self._attr_icon = "mdi:smoke-detector"
        elif device_class == BinarySensorDeviceClass.MOISTURE:
            self._attr_icon = "mdi:water-check"
        elif device_class == BinarySensorDeviceClass.GAS:
            self._attr_icon = "mdi:molecule-co-warning"
        elif device_class == BinarySensorDeviceClass.MOTION:
            self._attr_icon = "mdi:motion-sensor"
        elif device_class == BinarySensorDeviceClass.DOOR:
            self._attr_icon = "mdi:door-open"
        elif device_class == BinarySensorDeviceClass.PROBLEM:
            self._attr_icon = "mdi:alert-circle"
        else:
            self._attr_icon = "mdi:radiobox-marked"
    
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
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None

        prop = device.properties.get(self._property_identifier)
        if not prop or prop.value is None:
            return None

        # Handle boolean values
        if isinstance(prop.value, bool):
            return prop.value

        # Handle string alarm states
        if isinstance(prop.value, str):
            alarm_states = ["alarm", "alert", "active", "triggered", "true", "1"]
            return prop.value.lower() in alarm_states

        # Handle numeric values (0/1)
        if isinstance(prop.value, (int, float)):
            # For UnderVoltError: 0 = normal (False), non-zero = alarm (True)
            if "volt" in self._property_identifier.lower() or "error" in self._property_identifier.lower():
                return prop.value != 0
            return prop.value != 0

        return None
    
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
                attributes["raw_value"] = prop.value
        
        return attributes
