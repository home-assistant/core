"""Switch platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import DeviceProperty, HeimanDevice

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_ICONS
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Heiman switches based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Track existing entities to avoid duplicates
    existing_entities: set[str] = set()

    def _create_switches_for_devices() -> None:
        """Create switches for all devices and add new ones."""
        devices = coordinator.get_all_devices()
        new_switches = []

        for device in devices:
            for property_id, prop in device.properties.items():
                if not prop.writable:
                    continue

                # Use entity field from DeviceProperty
                if hasattr(prop, "entity") and prop.entity == "switch":
                    unique_id = f"{device.device_id}_{property_id}_switch"
                    if unique_id not in existing_entities:
                        new_switches.append(
                            HeimanSwitchEntity(
                                coordinator=coordinator,
                                device=device,
                                property_identifier=property_id,
                            )
                        )
                        existing_entities.add(unique_id)

        if new_switches:
            async_add_entities(new_switches)

    # Initial setup
    _create_switches_for_devices()

    # Listen for coordinator updates to add new devices dynamically
    entry.async_on_unload(coordinator.async_add_listener(_create_switches_for_devices))


class HeimanSwitchEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], SwitchEntity):
    """Representation of a Heiman switch entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
        property_identifier: str,
    ) -> None:
        """Initialize the switch.

        Args:
            coordinator: Data coordinator
            device: Heiman device
            property_identifier: Property identifier
        """
        super().__init__(coordinator)
        self._device = device
        self._property_identifier = property_identifier

        # Generate unique ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_switch"

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

        # Apply icon
        if prop:
            self._apply_icon(property_identifier, prop)
    
    def _apply_icon(self, property_identifier: str, prop: DeviceProperty | None) -> None:
        """Apply icon based on property type.

        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # First try to get from ENTITY_ICONS (using original case)
        icons_config = ENTITY_ICONS.get("switch", {})

        if property_identifier in icons_config:
            self._attr_icon = icons_config[property_identifier]
            return

        # If not found, try lowercase match
        prop_lower = property_identifier.lower()
        if prop_lower in icons_config:
            self._attr_icon = icons_config[prop_lower]
            return

        # Default switch icon
        self._attr_icon = "mdi:toggle-switch"
    
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
        """Return true if the switch is on."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None

        prop = device.properties.get(self._property_identifier)
        if not prop or prop.value is None:
            return None

        # Handle boolean values
        if isinstance(prop.value, bool):
            return prop.value

        # Handle string values
        if isinstance(prop.value, str):
            on_states = ["on", "true", "1", "opened", "active"]
            return prop.value.lower() in on_states

        # Handle numeric values
        if isinstance(prop.value, (int, float)):
            return prop.value != 0

        return None
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        # Write property via MQTT client using async_write_property method
        if self.coordinator.mqtt_client:
            # Build device info for child device detection
            # Use raw_data if available, fallback to device attributes
            device_info = {}
            if hasattr(self._device, "raw_data") and self._device.raw_data:
                device_info = {
                    "deviceType": self._device.raw_data.get("deviceType"),
                    "parentId": self._device.raw_data.get("parentId"),
                }
            else:
                device_info = {
                    "deviceType": getattr(self._device, "device_type", None),
                    "parentId": getattr(self._device, "parent_id", None),
                }

            await self.coordinator.mqtt_client.async_write_property(
                device_id=self._device.device_id,
                product_id=self._device.product_id,
                property_identifiers=[self._property_identifier],
                values={self._property_identifier: True},
                device_info=device_info,
            )
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        # Write property via MQTT client using async_write_property method
        if self.coordinator.mqtt_client:
            # Build device info for child device detection
            # Use raw_data if available, fallback to device attributes
            device_info = {}
            if hasattr(self._device, "raw_data") and self._device.raw_data:
                device_info = {
                    "deviceType": self._device.raw_data.get("deviceType"),
                    "parentId": self._device.raw_data.get("parentId"),
                }
            else:
                device_info = {
                    "deviceType": getattr(self._device, "device_type", None),
                    "parentId": getattr(self._device, "parent_id", None),
                }

            await self.coordinator.mqtt_client.async_write_property(
                device_id=self._device.device_id,
                product_id=self._device.product_id,
                property_identifiers=[self._property_identifier],
                values={self._property_identifier: False},
                device_info=device_info,
            )
    
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
