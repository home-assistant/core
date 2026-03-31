"""Switch platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.switch import SwitchEntity
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
    """Set up Heiman switches based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_all_devices()
    switches = []
    
    for device in devices:
        # 检查设备是否有可控制的开关属性
        for property_id, prop in device.properties.items():
            if not prop.writable:
                continue
            
            # Use entity field from DeviceProperty
            if hasattr(prop, 'entity') and prop.entity == "switch":
                switches.append(
                    HeimanSwitchEntity(
                        coordinator=coordinator,
                        device=device,
                        property_identifier=property_id,
                    )
                )
    
    async_add_entities(switches)


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
        
        # 生成唯一 ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_switch"
        
        # 设置名称
        prop = device.properties.get(property_identifier)
        self._attr_name = prop.name if prop else property_identifier
        
        # 获取设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer=device.manufacturer,
            model=device.model or device.product_id,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )
        
        # 应用图标
        self._apply_icon(property_identifier, prop)
    
    def _apply_icon(self, property_identifier: str, prop) -> None:
        """Apply icon based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # 首先尝试从 ENTITY_ICONS 获取（使用原始大小写）
        icons_config = ENTITY_ICONS.get("switch", {})

        if property_identifier in icons_config:
            self._attr_icon = icons_config[property_identifier]
            return
        
        # 如果未找到，尝试小写匹配
        prop_lower = property_identifier.lower()
        if prop_lower in icons_config:
            self._attr_icon = icons_config[prop_lower]
            _LOGGER.debug(f"Applied icon from lowercase config: {self._attr_icon} for {property_identifier}")
            return
        
        # 默认使用开关图标
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
    
    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None
        
        prop = device.properties.get(self._property_identifier)
        if not prop or prop.value is None:
            return None
        
        # 处理布尔值
        if isinstance(prop.value, bool):
            return prop.value
        
        # 处理字符串类型
        if isinstance(prop.value, str):
            on_states = ["on", "true", "1", "opened", "active"]
            return prop.value.lower() in on_states
        
        # 处理数值
        if isinstance(prop.value, (int, float)):
            return prop.value != 0
        
        return None
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
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
                    values={self._property_identifier: True},
                    device_info=device_info,
                )
                _LOGGER.debug(
                    "Successfully turned on %s for device %s via MQTT",
                    self._property_identifier,
                    self._device.device_id,
                )
            else:
                _LOGGER.error("MQTT client not available for turn_on")
        except Exception as err:
            _LOGGER.error(
                "Failed to turn on %s for device %s: %s",
                self._property_identifier,
                self._device.device_id,
                err,
            )
            raise
    
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
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
                    values={self._property_identifier: False},
                    device_info=device_info,
                )
                _LOGGER.debug(
                    "Successfully turned off %s for device %s via MQTT",
                    self._property_identifier,
                    self._device.device_id,
                )
            else:
                _LOGGER.error("MQTT client not available for turn_off")
        except Exception as err:
            _LOGGER.error(
                "Failed to turn off %s for device %s: %s",
                self._property_identifier,
                self._device.device_id,
                err,
            )
            raise
    
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
