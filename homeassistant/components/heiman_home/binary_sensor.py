"""Binary sensor platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import BINARY_SENSOR_DEVICE_CLASS_MAP, DOMAIN, ENTITY_ICONS
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman binary sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_all_devices()
    binary_sensors = []

    for device in devices:
        for property_id, prop in device.properties.items():
            # Check if property is readable and is binary_sensor type
            if not prop.readable:
                continue
            
            # Use entity field from DeviceProperty
            if hasattr(prop, 'entity') and prop.entity == "binary_sensor":
                binary_sensors.append(
                    HeimanBinarySensorEntity(
                        coordinator=coordinator,
                        device=device,
                        property_identifier=property_id,
                    )
                )

    async_add_entities(binary_sensors)



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
        
        # 生成唯一 ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_binary_sensor"
        
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
        
        # 根据属性类型设置设备类
        self._apply_device_class(property_identifier, prop)
        
        # 应用图标
        self._apply_icon(property_identifier, prop)
    
    def _apply_device_class(self, property_identifier: str, prop) -> None:
        """Apply device class based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        prop_lower = property_identifier
        # 尝试匹配已知的二进制传感器类型
        for key, device_class in BINARY_SENSOR_DEVICE_CLASS_MAP.items():
            if key in prop_lower:
                self._attr_device_class = BinarySensorDeviceClass(device_class)
                return
        
        # 默认使用通用类型
        if "alarm" in prop_lower:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
    
    def _apply_icon(self, property_identifier: str, prop) -> None:
        """Apply icon based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        prop_lower = property_identifier
        
        # 首先尝试从 ENTITY_ICONS 获取
        icons_config = ENTITY_ICONS.get("binary_sensor", {})

        if prop_lower in icons_config:
            self._attr_icon = icons_config[prop_lower]
            _LOGGER.debug(f"Applied icon: {self._attr_icon}")
            return
        
        # 根据设备类设置默认图标（使用 getattr 安全访问）
        device_class = getattr(self, '_attr_device_class', None)
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
        
        return device.online
    
    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None
        
        prop = device.properties.get(self._property_identifier)
        if not prop or prop.value is None:
            return None
        
        # 处理布尔值
        if isinstance(prop.value, bool):
            _LOGGER.debug(
                "BinarySensor %s (%s): value=%s (bool) -> is_on=%s",
                self._property_identifier,
                self._attr_name,
                prop.value,
                prop.value,
            )
            return prop.value
        
        # 处理字符串类型的报警状态
        if isinstance(prop.value, str):
            alarm_states = ["alarm", "alert", "active", "triggered", "true", "1"]
            result = prop.value.lower() in alarm_states
            _LOGGER.debug(
                "BinarySensor %s (%s): value='%s' (str) -> is_on=%s",
                self._property_identifier,
                self._attr_name,
                prop.value,
                result,
            )
            return result
        
        # 处理数值类型（0/1 或字符串数字）
        if isinstance(prop.value, (int, float)):
            # For UnderVoltError: 0 = normal (False), non-zero = alarm (True)
            if "volt" in self._property_identifier.lower() or "error" in self._property_identifier.lower():
                result = prop.value != 0
                _LOGGER.debug(
                    "BinarySensor %s (%s): value=%s (int/float) -> is_on=%s",
                    self._property_identifier,
                    self._attr_name,
                    prop.value,
                    result,
                )
                return result
            result = prop.value != 0
            _LOGGER.debug(
                "BinarySensor %s (%s): value=%s (int/float) -> is_on=%s",
                self._property_identifier,
                self._attr_name,
                prop.value,
                result,
            )
            return result
        
        _LOGGER.debug(
            "BinarySensor %s (%s): value=%s (unknown type %s) -> is_on=None",
            self._property_identifier,
            self._attr_name,
            prop.value,
            type(prop.value),
        )
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
