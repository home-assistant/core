"""Button platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ENTITY_ICONS
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman buttons based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_all_devices()
    buttons = []


    for device in devices:
        _LOGGER.debug(
            "Checking device %s (product_id: %s, name: %s) for buttons",
            device.device_id,
            device.product_id,
            device.device_name,
        )

        _LOGGER.debug("Device %s should have buttons based on product_id", device.device_id)
        
        for property_id, prop in device.properties.items():
            # Use entity field from DeviceProperty
            if hasattr(prop, 'entity') and prop.entity == "button":
                _LOGGER.debug(
                    "Found button entity for %s: %s (readable=%s, writable=%s, value=%s)",
                    device.device_id,
                    property_id,
                    prop.readable,
                    prop.writable,
                    prop.value,
                )
                buttons.append(
                    HeimanButtonEntity(
                        coordinator=coordinator,
                        device=device,
                        property_identifier=property_id,
                    )
                )
            elif hasattr(prop, 'entity'):
                _LOGGER.debug(
                    "Skipping non-button entity %s for %s: entity=%s",
                    property_id,
                    device.device_id,
                    prop.entity,
                )

    _LOGGER.info(
        "Created %d button entities for %d devices",
        len(buttons),
        len(devices),
    )
    async_add_entities(buttons)


def _is_button_property(prop) -> bool:
    """Check if property should be a button.
    
    Args:
        prop: Property object
        
    Returns:
        True if property should be a button
    """
    # Must be writable
    if not prop.writable:
        return False
    
    # Check data_type first
    if prop.data_type == "bool":
        return True
    
    # Check property identifier for known button types
    prop_lower = prop.identifier.lower()
    button_keywords = ["mute", "reset", "test", "check", "locate", "self-test"]
    return any(keyword in prop_lower for keyword in button_keywords)


class HeimanButtonEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], ButtonEntity):
    """Representation of a Heiman button entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
        property_identifier: str,
    ) -> None:
        """Initialize the button.
        
        Args:
            coordinator: Data coordinator
            device: Heiman device
            property_identifier: Property identifier
        """
        super().__init__(coordinator)
        self._device = device
        self._property_identifier = property_identifier
        
        # Generate unique ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_button"
        
        # Set name
        prop = device.properties.get(property_identifier)
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
        self._apply_icon(property_identifier, prop)
    
    def _apply_icon(self, property_identifier: str, prop) -> None:
        """Apply icon based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        from .const import ENTITY_ICONS
        
        # First try to get from ENTITY_ICONS (using original case)
        icons_config = ENTITY_ICONS.get("button", {})

        if property_identifier in icons_config:
            self._attr_icon = icons_config[property_identifier]
            return
        
        # If not found, try lowercase match
        prop_lower = property_identifier.lower()
        check_text = f"{prop_lower} {property_identifier}".lower()
        if check_text in icons_config:
            self._attr_icon = icons_config[check_text]
            _LOGGER.debug(f"Applied icon from lowercase config: {self._attr_icon} for {property_identifier}")
            return

        # Fallback icon detection based on property name
        if "led" in check_text or "indicator" in check_text:
            self._attr_icon = "mdi:led-on"
        elif "locate" in check_text or "page" in check_text or "find" in check_text:
            self._attr_icon = "mdi:radar"
        elif "mute" in check_text or "silent" in check_text:
            self._attr_icon = "mdi:volume-mute"
        elif "self-test" in check_text or "selftest" in check_text or "remotecheck" in check_text or "test" in check_text:
            self._attr_icon = "mdi:clipboard-check-outline"
        elif "power" in check_text or "switch" in check_text:
            self._attr_icon = "mdi:power-socket"
        else:
            self._attr_icon = "mdi:toggle-switch"
    
    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return False
        
        return device.online
    
    async def async_press(self) -> None:
        """Handle the button press."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            _LOGGER.error("Device %s not found for button press", self._device.device_id)
            return
        
        prop = device.properties.get(self._property_identifier)
        if not prop:
            _LOGGER.error("Property %s not found for button press", self._property_identifier)
            return
        
        # Get value to write (use default value 1 for boolean buttons)
        value_to_write = prop.value if prop.value is not None else 1
        
        # Write property via MQTT client using async_write_property method
        try:
            if self.coordinator.mqtt_client:
                # Build device info for child device detection
                # Use raw_data if available, fallback to device attributes
                device_info = {}
                if hasattr(device, 'raw_data') and device.raw_data:
                    device_info = {
                        "deviceType": device.raw_data.get("deviceType"),
                        "parentId": device.raw_data.get("parentId"),
                    }
                else:
                    device_info = {
                        "deviceType": getattr(device, 'device_type', None),
                        "parentId": getattr(device, 'parent_id', None),
                    }
                
                await self.coordinator.mqtt_client.async_write_property(
                    device_id=device.device_id,
                    product_id=device.product_id,
                    property_identifiers=[self._property_identifier],
                    values={self._property_identifier: value_to_write},
                    device_info=device_info,
                )
                _LOGGER.debug(
                    "Successfully pressed button %s for device %s via MQTT",
                    self._property_identifier,
                    device.device_id,
                )
            else:
                _LOGGER.error("MQTT client not available for button press")
        except Exception as err:
            _LOGGER.error(
                "Failed to press button %s for device %s: %s",
                self._property_identifier,
                device.device_id,
                err,
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
