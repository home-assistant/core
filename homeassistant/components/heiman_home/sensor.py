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

from .const import DOMAIN, ENTITY_ICONS, SENSOR_UNIT_MAP
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    devices = coordinator.get_all_devices()
    sensors = []

    for device in devices:
        # Create sensor for each readable property of each device
        for property_id, prop in device.properties.items():
            if not prop.readable:
                continue

            # Use entity field from DeviceProperty
            if hasattr(prop, "entity") and prop.entity == "sensor":
                sensors.append(
                    HeimanSensorEntity(
                        coordinator=coordinator,
                        device=device,
                        property_identifier=property_id,
                    )
                )

    async_add_entities(sensors)


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
        }

        # Try to match known properties
        config = None
        for key, cfg in property_mapping.items():
            if key in property_identifier.lower():
                config = SENSOR_UNIT_MAP.get(cfg["key"])
                break

        if config:
            device_class_value = config.get("device_class")
            if device_class_value:
                self._attr_device_class = SensorDeviceClass(device_class_value)
            self._attr_native_unit_of_measurement = config.get("unit")
            state_class_value = config.get("state_class", SensorStateClass.MEASUREMENT.value)
            if state_class_value:
                self._attr_state_class = SensorStateClass(state_class_value)
        elif prop:
            # Check if value is numeric before setting state_class
            if (
                prop.value is not None and isinstance(prop.value, (int, float))
            ) or prop.data_type in [
                "int",
                "double",
                "float",
                "long",
                "short",
                "byte",
                "number",
            ]:
                self._attr_state_class = SensorStateClass.MEASUREMENT
            # Non-numeric sensors should not have state_class set

    def _apply_icon(
        self, property_identifier: str, prop: DeviceProperty | None
    ) -> None:
        """Apply icon based on property type.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # First try to get from ENTITY_ICONS (using original case)
        icons_config = ENTITY_ICONS.get("sensor", {})

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

        return device.online

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
