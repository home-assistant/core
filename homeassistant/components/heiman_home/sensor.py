"""Sensor platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_UNIT_MAP, ENTITY_ICONS
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman sensors based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_all_devices()
    sensors = []
    
    for device in devices:
        # 为每个设备的每个可读属性创建传感器
        for property_id, prop in device.properties.items():
            if not prop.readable:
                continue
            
            # Use entity field from DeviceProperty
            if hasattr(prop, 'entity') and prop.entity == "sensor":
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
        
        # 生成唯一 ID
        self._attr_unique_id = f"{device.device_id}_{property_identifier}_sensor"
        
        # 设置名称
        self._attr_name = prop.name if (prop := device.properties.get(property_identifier)) else property_identifier
        
        # 获取设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer=device.manufacturer,
            model=device.model or device.product_id,
            sw_version=device.firmware_version,
            hw_version=device.hardware_version,
        )
        
        # 根据属性类型设置设备类和单位
        self._apply_sensor_config(property_identifier, prop)
        
        # 应用图标
        self._apply_icon(property_identifier, prop)
    
    def _apply_sensor_config(self, property_identifier: str, prop) -> None:
        """Apply sensor configuration based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # 映射常见属性到标准设备类
        property_mapping = {
            "temperature": {"device_class": SensorDeviceClass.TEMPERATURE, "key": "temperature"},
            "humidity": {"device_class": SensorDeviceClass.HUMIDITY, "key": "humidity"},
            "battery": {"device_class": SensorDeviceClass.BATTERY, "key": "battery"},
            "voltage": {"device_class": SensorDeviceClass.VOLTAGE, "key": "voltage"},
            "power": {"device_class": SensorDeviceClass.POWER, "key": "power"},
            "energy": {"device_class": SensorDeviceClass.ENERGY, "key": "energy"},
            "co_concentration": {"device_class": SensorDeviceClass.CO, "key": "co_concentration"},
            "signal_strength": {"device_class": SensorDeviceClass.SIGNAL_STRENGTH, "key": "signal_strength"},
        }
        
        # 尝试匹配已知属性
        config = None
        for key, cfg in property_mapping.items():
            if key in property_identifier.lower():
                config = SENSOR_UNIT_MAP.get(cfg["key"])
                break
        
        if config:
            self._attr_device_class = config.get("device_class")
            self._attr_native_unit_of_measurement = config.get("unit")
            self._attr_state_class = config.get("state_class", SensorStateClass.MEASUREMENT)
        else:
            # Check if value is numeric before setting state_class
            if prop.value is not None and isinstance(prop.value, (int, float)):
                self._attr_state_class = SensorStateClass.MEASUREMENT
            elif prop.data_type in ["int", "double", "float", "long", "short", "byte", "number"]:
                self._attr_state_class = SensorStateClass.MEASUREMENT
            # Non-numeric sensors should not have state_class set
    
    def _apply_icon(self, property_identifier: str, prop) -> None:
        """Apply icon based on property type.
        
        Args:
            property_identifier: Property identifier
            prop: Property object
        """
        # 首先尝试从 ENTITY_ICONS 获取（使用原始大小写）
        icons_config = ENTITY_ICONS.get("sensor", {})

        if property_identifier in icons_config:
            self._attr_icon = icons_config[property_identifier]
            return
        
        # 如果未找到，尝试小写匹配
        prop_lower = property_identifier.lower()
        if prop_lower in icons_config:
            self._attr_icon = icons_config[prop_lower]
            return
        
        # 根据设备类设置默认图标（使用 getattr 安全访问）
        device_class = getattr(self, '_attr_device_class', None)
        if device_class == "temperature":
            self._attr_icon = "mdi:thermometer"
        elif device_class == "humidity":
            self._attr_icon = "mdi:water-percent"
        elif device_class == "battery":
            self._attr_icon = "mdi:battery"
        elif device_class == "signal_strength":
            self._attr_icon = "mdi:signal"
        elif device_class == "voltage":
            self._attr_icon = "mdi:flash-triangle"
        elif device_class == "power":
            self._attr_icon = "mdi:flash"
        elif device_class == "energy":
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
    def native_value(self) -> Any:
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
