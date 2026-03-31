"""Select platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALARM_SOUND_DISPLAY_NAMES, ALARM_SOUND_OPTIONS, DOMAIN, ENTITY_ICONS
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman selects based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_all_devices()
    selects = []
    
    for device in devices:
        for property_id, prop in device.properties.items():
            # Use entity field from DeviceProperty
            if hasattr(prop, 'entity') and prop.entity == "select":
                selects.append(
                    HeimanSelectEntity(
                        coordinator=coordinator,
                        device=device,
                        property_identifier=property_id,
                    )
                )

    async_add_entities(selects)


def _is_select_property(prop) -> bool:
    """Check if property should be a select entity.
    
    Args:
        prop: Property object
        
    Returns:
        True if property should be a select
    """
    # Must be writable
    if not prop.writable:
        return False
    
    # Check if it's an enum type
    if prop.data_type == "enum":
        return True
    
    # Check property identifier for known select types
    prop_lower = prop.identifier.lower()
    select_keywords = ["mode", "option", "setting", "level", "speed"]
    return any(keyword in prop_lower for keyword in select_keywords)


class HeimanSelectEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], SelectEntity):
    """Representation of a Heiman select entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
        property_identifier: str,
    ) -> None:
        """Initialize the select entity.
        
        Args:
            coordinator: Data coordinator
            device: Heiman device
            property_identifier: Property identifier
        """
        super().__init__(coordinator)
        self._device = device
        self._property_identifier = property_identifier
        
        # Generate unique ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_select"
        
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
        
        # Store value_list mapping (description -> value) and reverse (value -> description)
        self._value_list = {}
        self._reverse_value_list = {}
        
        # Set options and value mappings
        self._setup_property_options(prop)
        
        # Apply icon
        self._apply_icon(property_identifier, prop)
        
        # Initialize current option from coordinator cache
        self._current_option = None
        self._update_current_option_from_cache()
    
    def _setup_property_options(self, prop) -> None:
        """Setup options and value mappings for the property.
        
        Args:
            prop: Property object
        """
        # Try to get options from const if it's a known property type
        if self._property_identifier == "AlarmSoundOption":
            # Use display names as options (user-friendly strings)
            self._attr_options = list(ALARM_SOUND_DISPLAY_NAMES.values())
            
            # Setup value_list mapping (display_name -> API_value)
            # API returns numeric values: 0=fast, 1=medium, 2=slow
            self._value_list = {
                "Fast Beep": "0",
                "Medium Beep": "1",
                "Slow Beep": "2",
            }
            # Setup reverse_value_list mapping (API_value -> display_name)
            self._reverse_value_list = {
                "0": "Fast Beep",
                "1": "Medium Beep",
                "2": "Slow Beep",
            }
            _LOGGER.debug(
                "AlarmSoundOption initialized: options=%s, value_list=%s, reverse_value_list=%s",
                self._attr_options,
                self._value_list,
                self._reverse_value_list,
            )
        else:
            # Default options based on common enums
            self._attr_options = ["disarmed", "armed_home", "armed_away", "armed_night"]
            # Setup value_list mapping for arm modes
            self._value_list = {
                "disarmed": "disarmed",
                "armed_home": "home",
                "armed_away": "away",
                "armed_night": "night",
            }
            self._reverse_value_list = {
                "disarmed": "disarmed",
                "home": "armed_home",
                "away": "armed_away",
                "night": "armed_night",
            }
    
    def _get_description(self, value) -> str | None:
        """Get description (option text) from value.
        
        Args:
            value: Raw value from API
            
        Returns:
            Display description or None
        """
        if value is None:
            return None
            
        # Try reverse_value_list first (value -> description)
        str_value = str(value)
        
        # Debug logging for AlarmSoundOption
        if self._property_identifier == "AlarmSoundOption":
            _LOGGER.debug(
                "AlarmSoundOption _get_description: value=%s, str_value=%s, reverse_value_list=%s",
                value,
                str_value,
                self._reverse_value_list,
            )
        
        if str_value in self._reverse_value_list:
            result = self._reverse_value_list[str_value]
            if self._property_identifier == "AlarmSoundOption":
                _LOGGER.debug(
                    "AlarmSoundOption found in reverse_value_list: %s -> %s",
                    str_value,
                    result,
                )
            return result
        
        # Fallback: try value_list (description -> value) in case they're the same
        for desc, val in self._value_list.items():
            if str(val) == str_value:
                if self._property_identifier == "AlarmSoundOption":
                    _LOGGER.debug(
                        "AlarmSoundOption found in value_list: %s -> %s",
                        str_value,
                        desc,
                    )
                return desc
        
        # If no mapping found, return the value itself as string
        if self._property_identifier == "AlarmSoundOption":
            _LOGGER.warning(
                "AlarmSoundOption no mapping found for value: %s, returning as string",
                str_value,
            )
        return str_value
    
    def _get_value(self, description: str):
        """Get value from description (option text).
        
        Args:
            description: Option description
            
        Returns:
            Raw value for API
        """
        # Try value_list first (description -> value)
        if description in self._value_list:
            result = self._value_list[description]
            if self._property_identifier == "AlarmSoundOption":
                _LOGGER.debug(
                    "AlarmSoundOption _get_value: %s -> %s",
                    description,
                    result,
                )
            return result
        
        # If not found, return the description itself
        if self._property_identifier == "AlarmSoundOption":
            _LOGGER.warning(
                "AlarmSoundOption _get_value no mapping found for: %s, returning as is",
                description,
            )
        return description
    
    def _apply_icon(self, property_identifier: str, prop) -> None:
        """Apply icon based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # First try to get from ENTITY_ICONS (using original case)
        icons_config = ENTITY_ICONS.get("select", {})

        if property_identifier in icons_config:
            self._attr_icon = icons_config[property_identifier]
            return
        
        # If not found, try lowercase match
        prop_lower = property_identifier.lower()
        if prop_lower in icons_config:
            self._attr_icon = icons_config[prop_lower]
            _LOGGER.debug(f"Applied icon from lowercase config: {self._attr_icon} for {property_identifier}")
            return
        
        # Default icon
        self._attr_icon = "mdi:volume-high"
    
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
    def current_option(self) -> str | None:
        """Return the current selected option.
        
        This should only return information from memory (not do I/O).
        """
        return self._current_option
    
    def _update_current_option_from_cache(self) -> bool:
        """Update current option from coordinator cache (synchronous).
        
        Returns True if state was updated from cache, False if cache miss or no change.
        """
        device_id = self._device.device_id
        property_id = self._property_identifier
        
        if self.coordinator and hasattr(self.coordinator, "get_device_property"):
            cached_value = self.coordinator.get_device_property(device_id, property_id)
            
            if cached_value is not None:
                # Convert value to description (option text)
                old_option = self._current_option
                self._current_option = self._get_description(value=cached_value)
                
                # Debug logging for AlarmSoundOption
                if self._property_identifier == "AlarmSoundOption":
                    _LOGGER.debug(
                        "AlarmSoundOption _update_current_option_from_cache: old=%s, new=%s, cached_value=%s",
                        old_option,
                        self._current_option,
                        cached_value,
                    )
                
                if self._current_option != old_option:
                    _LOGGER.debug(
                        "Select %s current_option updated from cache: %s (value=%s)",
                        self._attr_name,
                        self._current_option,
                        cached_value,
                    )
                    return True
                else:
                    _LOGGER.debug(
                        "Select %s current_option unchanged: %s (value=%s)",
                        self._attr_name,
                        self._current_option,
                        cached_value,
                    )
        return False
    
    async def async_select_option(self, option: str) -> None:
        """Change the selected option.
        
        Args:
            option: Selected option
        """
        # Get the actual value for this option
        value = self._get_value(description=option)
        
        _LOGGER.debug(
            "Select %s setting option: %s -> value: %s",
            self._attr_name,
            option,
            value,
        )
        
        try:
            # Write property via MQTT client using async_write_property method
            if self.coordinator.mqtt_client:
                # Build device info for child device detection
                # Use raw_data if available, fallback to device attributes
                device_info = {}
                if hasattr(self._device, 'raw_data') and self._device.raw_data:
                    device_info = {
                        "deviceType": self._device.raw_data.get("deviceType"),
                        "parentId": self._device.raw_data.get("parentId"),
                    }
                else:
                    device_info = {
                        "deviceType": getattr(self._device, 'device_type', None),
                        "parentId": getattr(self._device, 'parent_id', None),
                    }
                
                await self.coordinator.mqtt_client.async_write_property(
                    device_id=self._device.device_id,
                    product_id=self._device.product_id,
                    property_identifiers=[self._property_identifier],
                    values={self._property_identifier: value},
                    device_info=device_info,
                )
                _LOGGER.debug(
                    "Successfully set %s to %s for device %s via MQTT",
                    self._property_identifier,
                    value,
                    self._device.device_id,
                )
            else:
                _LOGGER.error("MQTT client not available for select option")
        except Exception as err:
            _LOGGER.error(
                "Failed to set %s for device %s: %s",
                self._property_identifier,
                self._device.device_id,
                err,
            )
            raise
        
        # Update current option immediately for better UX
        self._current_option = option
        self.async_write_ha_state()
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).
        
        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        try:
            device_id = self._device.device_id
            property_id = self._property_identifier
            
            _LOGGER.debug(
                "Select %s received coordinator update notification for device %s, property %s",
                self._attr_name,
                device_id,
                property_id,
            )
            
            # Update current option from cache and always write state
            # This ensures HA state is synchronized even if value hasn't changed
            self._update_current_option_from_cache()
            
            # Debug logging for AlarmSoundOption
            if self._property_identifier == "AlarmSoundOption":
                _LOGGER.debug(
                    "AlarmSoundOption _handle_coordinator_update: current_option=%s",
                    self._current_option,
                )
            
            # Write the new state to Home Assistant immediately
            _LOGGER.debug(
                "Select %s writing state to HA: %s",
                self._attr_name,
                self._current_option,
            )
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error(
                "Error handling coordinator update for %s: %s",
                self._attr_name,
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
