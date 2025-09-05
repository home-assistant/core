# file: number.py
"""Platform for Hisense AC number integration."""
from __future__ import annotations

import logging
from typing import Any, Callable

from homeassistant.components.number import NumberEntity, NumberDeviceClass, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import Event
from homeassistant.helpers.dispatcher import callback

from .const import DOMAIN, StatusKey, MIN_TEMP_WATER, MAX_TEMP_WATER
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .api import HisenseApiClient
from .models import DeviceInfo as HisenseDeviceInfo

_LOGGER = logging.getLogger(__name__)

# Define number types
NUMBER_TYPES = {
    "t_zone1water_settemp1": {
        "key": "t_zone1water_settemp1",
        "name": "1温区设置值",
        "icon": "mdi:thermometer",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "mode": NumberMode.AUTO,
        "unit": "°C",
        "min_value": 16,
        "max_value": 32,
        "step": 0.5,
        "description": "Set 1温区设置值"
    },
    "t_zone2water_settemp2": {
        "key": "t_zone2water_settemp2",
        "name": "2温区设置值",
        "icon": "mdi:thermometer",
        "device_class": NumberDeviceClass.TEMPERATURE,
        "mode": NumberMode.AUTO,
        "unit": "°C",
        "min_value": 16,
        "max_value": 32,
        "step": 0.5,
        "description": "Set 2温区设置值"
    }
}

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense AC number platform."""
    coordinator: HisenseACPluginDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    try:
        # Get devices from coordinator
        devices = coordinator.data
        _LOGGER.debug("Setting up numbers with coordinator data: %s", devices)

        if not devices:
            _LOGGER.warning("No devices found in coordinator data")
            return

        entities = []
        for device_id, device in devices.items():
            _LOGGER.debug("Processing device for numbers: %s", device.to_dict())

            if isinstance(device, HisenseDeviceInfo) and device.is_devices():
                # Add numbers for each supported feature
                for number_type, number_info in NUMBER_TYPES.items():
                    # Check if the device supports this attribute
                    parser = coordinator.api_client.parsers.get(device.device_id)
                    if device.has_attribute(number_info["key"], parser):
                        if device.status.get("f_zone2_select") == "0" and number_type == "t_zone2water_settemp2":
                            continue
                        _LOGGER.info(
                            "Adding %s number for device: %s",
                            number_info["name"],
                            device.name
                        )
                        entity = HisenseNumber(
                            coordinator,
                            device,
                            number_type,
                            number_info
                        )
                        entities.append(entity)
            else:
                _LOGGER.warning(
                    "Skipping unsupported device: %s-%s (%s)",
                    getattr(device, 'type_code', None),
                    getattr(device, 'feature_code', None),
                    getattr(device, 'name', None)
                )

        if not entities:
            _LOGGER.warning("No supported numbers found")
            return

        _LOGGER.info("Adding %d number entities", len(entities))
        async_add_entities(entities)

    except Exception as err:
        _LOGGER.error("Failed to set up number platform: %s", err)
        raise

class HisenseNumber(CoordinatorEntity, NumberEntity):
    """Representation of a Hisense AC number."""

    _attr_has_entity_name = True
    _temperatureRange = [
        # [ModeType.COOL] 制冷
        [16, 30, 5, 27, None, None],
        # [ModeType.HEAT] 加热
        [16, 30, 25, 65, None, None],
        # [ModeType.AUTO] 自动
        [16, 30, 5, 65, None, None],
        # [ModeType.COOL_DHW] 制冷 + 制热水
        [16, 30, 5, 27, 35, 55],
        # [ModeType.HEAT_DHW] 加热 + 制热水
        [16, 30, 25, 65, 35, 55],
        # [ModeType.AUTO_DHW] 自动 + 制热水
        [16, 30, 5, 65, 35, 55],
        # [ModeType.ONLY_DHW] 制热水
        [None, None, None, None, 35, 55],
    ]

    def __init__(
        self,
        coordinator: HisenseACPluginDataUpdateCoordinator,
        device: HisenseDeviceInfo,
        number_type: str,
        number_info: dict,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.current_mode = None
        self._device_id = device.puid
        self._number_type = number_type
        self._number_info = number_info
        self._number_key = number_info["key"]
        self._attr_unique_id = f"{device.device_id}_{number_type}"
        self._attr_name = number_info["name"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Hisense",
            model=f"{device.type_name} ({device.feature_name})",
        )
        self._attr_icon = number_info["icon"]
        self._attr_device_class = number_info.get("device_class")
        self._attr_mode = number_info.get("mode")
        self._attr_native_unit_of_measurement = number_info.get("unit")
        self._attr_native_min_value = float(number_info.get("min_value"))
        self._attr_native_max_value = float(number_info.get("max_value"))
        self._attr_native_step = float(number_info.get("step"))
        self._attr_entity_registry_enabled_default = True

        # 初始化时更新一次温度范围
        self._cached_device = None
        self._last_t_zone1_temp = None
        self._last_mode = None
        self._update_temperature_range()

    @property
    def name(self) -> str:
        """动态获取翻译后的名称"""
        hass = self.hass
        translation_key = self._number_type  # 使用开关类型作为键
        current_lang = hass.config.language
        translations = hass.data.get(f"{DOMAIN}.translations", {}).get(current_lang, {})
        translated_name = translations.get(translation_key, self._number_info["name"])
        return translated_name

    @property
    def _device(self):
        """Get current device data from coordinator."""
        return self.coordinator.get_device(self._device_id)

    def _get_mode_index(self, mode: str) -> int | None:
        """获取模式的索引"""
        mode_map = {
            "1": 0,
            "0": 1,
            "15": 2,
            "5": 3,
            "16": 4,
            "6": 5,
            "3": 6,
        }
        return mode_map.get(mode)

    def _update_temperature_range(self):
        """Update the temperature range based on the current mode and feature_code."""
        device = self.coordinator.get_device(self._device_id)
        if not device:
            return

        current_mode = device.get_status_value("t_work_mode")
        t1_temp = device.get_status_value("t_zone1water_settemp1")

        # 如果模式和温区1温度未变，则无需更新
        if current_mode == self._last_mode and t1_temp == self._last_t_zone1_temp:
            return

        self._last_mode = current_mode
        self._last_t_zone1_temp = t1_temp

        mode_index = self._get_mode_index(current_mode)
        if mode_index is None:
            _LOGGER.warning("No temperature range found for mode %s", current_mode)
            return

        temperatures = self._temperatureRange[mode_index]
        if self._number_type == "t_zone2water_settemp2":
            min_val = float(temperatures[2]) if temperatures[2] is not None else MIN_TEMP_WATER
            max_val = float(t1_temp) if t1_temp is not None else MAX_TEMP_WATER
        else:
            min_val = float(temperatures[2]) if temperatures[2] is not None else MIN_TEMP_WATER
            max_val = float(temperatures[3]) if temperatures[3] is not None else MAX_TEMP_WATER

        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # 基础可用性检查（设备在线）
        if not self._device or not self._device.is_online:
            return False
        # 新增：设备关机状态下不可用
        power_status = self._device.get_status_value("t_power")
        if power_status != "1":
            _LOGGER.debug("设备已关机，实体不可用")
            return False
        current_mode = self._device.get_status_value("t_work_mode")
        # 判断自动模式
        if current_mode in ["15", "3", "16"]:
            _LOGGER.debug("设备处于自动模式，温度控制不可用")
            return False

        # 判断温区2在制冷或制冷+生活热水模式下是否禁用
        if self._number_type == "t_zone2water_settemp2":
            if current_mode in ["1", "5"]:  # 对应制冷和制冷+生活热水模式
                _LOGGER.debug("当前模式 %s 禁用温区2控制", current_mode)
                return False

        return True

    @property
    def native_value(self) -> float | None:
        """Return the number value."""
        device = self.coordinator.get_device(self._device_id)
        if not device or not device.is_online:
            return None

        value = device.get_status_value(self._number_key)
        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()

        # 监听设备数据更新
        self.async_on_remove(
            self.coordinator.async_add_listener(self._handle_coordinator_update)
        )

    def _handle_coordinator_update(self) -> None:
        """Handle data update from coordinator."""
        self._update_temperature_range()
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new target value."""
        try:
            # Ensure the value is within the valid range
            if value < self._attr_native_min_value or value > self._attr_native_max_value:
                _LOGGER.error("Value out of range: %s", value)
                return

            # Convert value to integer before sending to device
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={self._number_key: str(value)},
            )
        except Exception as err:
            _LOGGER.error("Failed to set %s: %s", self._attr_name, err)
