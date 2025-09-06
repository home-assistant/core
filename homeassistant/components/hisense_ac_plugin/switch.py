"""Platform for Hisense AC switch integration."""
from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.core import Event
from homeassistant.helpers.dispatcher import callback

from .const import DOMAIN, StatusKey
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .api import HisenseApiClient
from .models import DeviceInfo as HisenseDeviceInfo

_LOGGER = logging.getLogger(__name__)

# Define switch types
SWITCH_TYPES = {
    "quiet_mode": {
        "key": StatusKey.QUIET,
        "name": "Quiet Mode",
        "icon_on": "mdi:volume-off",
        "icon_off": "mdi:volume-high",
        "description": "Toggle quiet mode"
    },
    "rapid_mode": {
        "key": StatusKey.RAPID,
        "name": "Rapid Mode",
        "icon_on": "mdi:speedometer",
        "icon_off": "mdi:speedometer-slow",
        "description": "Toggle rapid (powerful) mode"
    },
    "8heat_mode": {
        "key": StatusKey.EIGHTHEAT,
        "name": "8heat Mode",
        "icon_on": "mdi:fire",
        "icon_off": "mdi:fire-off",
        "description": "Toggle 8heat mode"
    }
    # ,
    # "eco_mode": {
    #     "key": StatusKey.ECO,
    #     "name": "Eco Mode",
    #     "icon_on": "mdi:leaf",
    #     "icon_off": "mdi:leaf-off",
    #     "description": "Toggle eco mode"
    # }
}

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense AC switch platform."""
    coordinator: HisenseACPluginDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    try:
        # Get devices from coordinator
        devices = coordinator.data
        _LOGGER.debug("Setting up switches with coordinator data: %s", devices)

        if not devices:
            _LOGGER.warning("No devices found in coordinator data")
            return

        entities = []
        for device_id, device in devices.items():
            _LOGGER.debug("Processing device for switches: %s", device.to_dict())

            if isinstance(device, HisenseDeviceInfo) and device.is_devices():
                # Add switches for each supported feature
                for switch_type, switch_info in SWITCH_TYPES.items():
                    # Check if the device supports this attribute
                    parser = coordinator.api_client.parsers.get(device.device_id)
                    if device.has_attribute(switch_info["key"], parser):
                        _LOGGER.info(
                            "Adding %s switch for device: %s",
                            switch_info["name"],
                            device.name
                        )
                        static_data = coordinator.api_client.static_data.get(device.device_id)
                        if static_data:
                            rapid_mode = static_data.get("Super_function")
                            quiet_mode = static_data.get("Mute_mode_function")
                            if switch_type == "rapid_mode" and rapid_mode != "1":
                                continue
                            if switch_type == "quiet_mode" and quiet_mode != "1":
                                continue
                        else:
                            if not device.status.get(switch_info["key"]):
                                continue
                        _LOGGER.info("当前设备: %s: %s",device.feature_code,device.status)
                        #跟cl对齐，去掉200的静音
                        if switch_type == "quiet_mode":
                            if device.feature_code == 200 or device.feature_code == "200":
                                continue
                        entity = HisenseSwitch(
                            coordinator,
                            device,
                            switch_type,
                            switch_info
                        )
                        entities.append(entity)

                # 新增：处理除湿机风速开关
                if device.type_code == "007":
                    _LOGGER.info("除湿机添加风速进入: %s", device.feature_code)
                    parser = coordinator.api_client.parsers.get(device.device_id)
                    _LOGGER.info("除湿机添加风速进入: %s: %s", device.feature_code, parser.attributes)
                    if parser and "t_fan_speed" in parser.attributes:
                        _LOGGER.info("除湿机添加风速进入: %s", device.feature_code)
                        fan_attr = parser.attributes['t_fan_speed']
                        _LOGGER.info("除湿机添加风速进入: %s: %s", device.feature_code,
                                     parser.attributes.get("t_fan_speed"))
                        static_data = coordinator.api_client.static_data.get(device.device_id)
                        if static_data:
                            _LOGGER.info("获取到静态数据: %s: %s", device.feature_code, static_data)
                            # 构建功能标志字典（默认设为"0"）
                            feature_flags = {
                                "自动": static_data.get("Wind_speed_gear_selection_auto", "0"),
                                "中风": static_data.get("Wind_speed_gear_selection_middle", "0"),
                                "高风": static_data.get("Wind_speed_gear_selection_high", "0"),
                                "低风": static_data.get("Wind_speed_gear_selection_low", "0")
                            }

                            # 创建标签到数值的反向映射
                            reverse_map = {'低风': '0', '高风': '1', '中风': '3', '自动': '2'}

                            # 遍历所有预定义风速标签
                            for label in ["自动", "中风", "高风", "低风"]:
                                # 判断是否支持该风速
                                if feature_flags[label] != "1":
                                    _LOGGER.debug(f"设备 {device.name} 不支持 {label} 风速功能，跳过创建")
                                    continue

                                # 获取对应的数值
                                value_str = reverse_map.get(label)
                                if value_str is None:
                                    _LOGGER.warning(f"设备 {device.name} 风速标签 {label} 未找到对应数值，跳过创建")
                                    continue

                                # 创建开关实体
                                switch_type = f"fan_speed_{label.lower().replace(' ', '_')}"
                                switch_info = {
                                    "key": fan_attr.key,
                                    "name": f"{label} 风速",
                                    "icon_on": "mdi:fan",
                                    "icon_off": "mdi:fan-off",
                                    "description": f"切换到 {label} 风速",
                                    "expected_value": value_str
                                }
                                entity = HisenseSwitch(
                                    coordinator,
                                    device,
                                    switch_type,
                                    switch_info,
                                    expected_value=value_str
                                )
                                entities.append(entity)
                        else:
                            for value_str, label in fan_attr.value_map.items():
                                _LOGGER.info("除湿机添加风速进入: %s: %s: %s", device.feature_code, value_str, label)
                                switch_type = f"fan_speed_{label.lower().replace(' ', '_')}"
                                switch_info = {
                                    "key": fan_attr.key,
                                    "name": f"{label} 风速",
                                    "icon_on": "mdi:fan",
                                    "icon_off": "mdi:fan-off",
                                    "description": f"切换到 {label} 风速",
                                    "expected_value": value_str
                                }
                                entity = HisenseSwitch(
                                    coordinator,
                                    device,
                                    switch_type,
                                    switch_info,
                                    expected_value=value_str
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
            _LOGGER.warning("No supported switches found")
            return

        _LOGGER.info("Adding %d switch entities", len(entities))
        async_add_entities(entities)

    except Exception as err:
        _LOGGER.error("Failed to set up switch platform: %s", err)
        raise

class HisenseSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Hisense AC switch."""

    _attr_has_entity_name = True
    _debounce_delay = 10

    def __init__(
        self,
        coordinator: HisenseACPluginDataUpdateCoordinator,
        device: HisenseDeviceInfo,
        switch_type: str,
        switch_info: dict,
        expected_value: str = None  # 新增参数
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._last_action_time = 0  # 上次操作时间
        self.device = device
        self.cached = False
        self.feature_code = device.feature_code
        self._switch_info = switch_info
        self._device_id = device.puid
        self._switch_type = switch_type
        self._switch_key = switch_info["key"]
        self._attr_unique_id = f"{device.device_id}_{switch_type}"
        self._attr_name = switch_info["name"]
        self._last_cloud_value = None  # 新增：存储最后一次云端推送的状态值
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Hisense",
            model=f"{device.type_name} ({device.feature_name})",
        )
        self._attr_icon = switch_info["icon_off"]
        self._attr_entity_registry_enabled_default = True
        self._expected_value = expected_value  # 新增属性

    async def async_added_to_hass(self):
        """当实体被添加到 Home Assistant 时调用。"""
        await super().async_added_to_hass()
        # 订阅设备状态变化事件
        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self.entity_id],
                self._handle_device_state_change
            )
        )

    @callback
    def _handle_device_state_change(self, event: Event) -> None:
        """处理设备状态变化事件。"""
        _LOGGER.info("设备状态变化事件: %s", event.data)
        new_state = event.data.get("new_state")
        if new_state:
            # 动态更新实体名称
            # self._update_entity_name()
            # 使用 hass.add_job 安全地调度更新到事件循环线程
            self.hass.add_job(self._async_schedule_update)

    async def _async_schedule_update(self):
        """异步调度更新实体状态。"""
        await self.async_schedule_update_ha_state(True)

    # def _update_entity_name(self):
    #     """根据设备状态动态更新实体名称。"""
    #     hass = self.hass
    #     current_lang = hass.config.language
    #     translations = hass.data.get(f"{DOMAIN}.translations", {}).get(current_lang, {})
    #
    #     # 基础翻译键
    #     translation_key = self._switch_type
    #
    #     # 特殊处理强力模式名称：根据当前模式动态调整翻译键
    #     if self._switch_type == "rapid_mode":
    #         current_mode = self._device.get_status_value(StatusKey.MODE) if self._device else None
    #         _LOGGER.info("当前模式: %s", current_mode)
    #         if current_mode == "2":  # 假设 "1" 对应制冷模式（需根据实际 StatusKey 的值调整）
    #             translation_key = "rapid_mode_cold"
    #         elif current_mode == "1":  # 假设 "2" 对应制热模式（需根据实际 StatusKey 的值调整）
    #             translation_key = "rapid_mode_heat"
    #     _LOGGER.info("翻译键: %s", translation_key)
    #     # 获取翻译后的名称
    #     translated_name = translations.get(translation_key, self._switch_info["name"])
    #     _LOGGER.info("翻译后的名称: %s", translated_name)
    #     self._attr_name = translated_name

    @property
    def name(self) -> str:
        """动态获取翻译后的名称"""
        hass = self.hass
        translation_key = self._switch_type  # 使用开关类型作为键
        current_lang = hass.config.language
        translations = hass.data.get(f"{DOMAIN}.translations", {}).get(current_lang, {})
        translated_name = translations.get(translation_key, self._switch_info["name"])
        return translated_name
    @property
    def _device(self):
        """Get current device data from coordinator."""
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        _LOGGER.info("设备 %s 是否可用: %s", self.feature_code, self._device.is_onOff)  # 调用方法并获取返回值
        if not self._device or not self._device.is_online or not self._device.is_onOff:
            return False

        # Check if the switch should be hidden based on the current mode
        current_mode = self._device.get_status_value(StatusKey.MODE)
        if self._switch_type == "rapid_mode":
            if current_mode in ["0", "4", "3"]:  # Assuming "0" is AUTO, "1" is FAN, and "3" is DEHUMIDIFY
                return False
        elif self._switch_type == "quiet_mode":
            if current_mode in ["4", "3"]:  # Assuming "0" is AUTO and "1" is FAN
                return False
        elif self._switch_type == "8heat_mode":
            if current_mode not in ["1"]:
                return False
        elif self._switch_type == "eco_mode":
            # 新增feature_code判断逻辑
            if self.device.feature_code == "199":
                if current_mode in ["4", "0"]:  # 特殊处理feature_code=199时的mode检查
                    return False
            else:
                if current_mode in ["4"]:  # 其他设备保持原逻辑
                    return False
        elif self.device.type_code == "007" and self._switch_type.startswith("fan_speed_"):
            if current_mode in ["2"]:
                return False
            # 新增逻辑：除湿机开启时风速开关不可选中
            if self.is_on:
                return False

        return True

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        current_time = time.time()

        # 检查是否处于防跳变时间窗口内
        if current_time - self._last_action_time < self._debounce_delay:
            _LOGGER.info("当前处于防跳变时间窗口内，使用缓存状态: %s", self.cached)
            return self.cached

        # 防跳变时间窗口结束，恢复使用云端状态
        _LOGGER.info("防跳变时间窗口结束，恢复使用云端状态")
        self.cached = False  # 重置缓存标志
        if self.device.type_code == "007" and self._switch_type.startswith("fan_speed_"):
            # 提取风速标签（如"低风"）
            fan_speed_label = self._switch_type.split("_")[-1]  # 例如"fan_speed_低风" → "低风"

            # 通过value_map将中文标签映射到数值
            value_map = {
                "自动": "2",
                "中风": "3",
                "高风": "1",
                "低风": "0"
            }
            expected_value = value_map.get(fan_speed_label)  # 获取对应的数值

            # 获取当前设备风速值
            current_value = self._device.get_status_value("t_fan_speed")

            _LOGGER.info("除湿机风速判断: 当前值=%s, 期望值=%s", current_value, expected_value)

            # 比较当前值与期望值
            return current_value == expected_value
        else:
            # 其他开关类型
            value = self._device.get_status_value(self._switch_key)
            self._last_cloud_value = value  # 保存最后一次云端状态值
            _LOGGER.info("从云端获取到的状态值: %s", value)
            return value == "1"

    @property
    def icon(self) -> str:
        """Correctly handle fan speed switch icons"""
        if self._switch_type.startswith("fan_speed_"):
            # Use the icon from switch_info passed during initialization
            return self._switch_info["icon_on"] if self.is_on else self._switch_info["icon_off"]
        else:
            # Use predefined icons for other switches
            switch_info = SWITCH_TYPES.get(self._switch_type, {})
            return switch_info.get("icon_on", "mdi:fan") if self.is_on else switch_info.get("icon_off", "mdi:fan-off")

    # 修改 switch.py 中的 HisenseSwitch 类的 async_turn_on 方法：


    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        current_time = time.time()
        self.cached = True
        self._last_action_time = current_time
        self._last_cloud_value = None  # 重置云端状态值（因为即将发送新的控制指令）

        try:
            if self._switch_type.startswith("fan_speed_"):
                value = self._expected_value  # 使用预设的期望值（如"0","1"等）
            else:
                value = "1"  # 其他开关保持原逻辑

            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={self._switch_key: value},
            )

            # 强制更新本地缓存状态（不等待Coordinator的更新）
            if self._switch_type.startswith("fan_speed_"):
                # 风速开关需要根据value设置对应的属性
                fan_speed_key = self._switch_info["key"]
                self._device.status[fan_speed_key] = value
            else:
                self._device.status[self._switch_key] = value

            # 更新上次操作时间
            self._last_action_time = current_time

            # 强制更新状态
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on %s: %s", self._attr_name, err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        current_time = time.time()
        self.cached = False
        self._last_action_time = current_time
        self._last_cloud_value = None  # 重置云端状态值（因为即将发送新的控制指令）

        try:
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={self._switch_key: "0"},
            )

            # 强制更新本地缓存状态（不等待Coordinator的更新）
            self._device.status[self._switch_key] = "0"

            # 更新上次操作时间
            self._last_action_time = current_time

            # 强制更新状态
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off %s: %s", self._attr_name, err)

    async def _async_schedule_update(self):
        """异步调度更新实体状态，同时处理防跳变逻辑。"""
        current_time = time.time()

        # 检查是否处于防跳变时间窗口内
        if current_time - self._last_action_time < self._debounce_delay:
            _LOGGER.info("防跳变时间窗口内，延后更新状态")
            # 计算剩余时间
            remaining_time = self._debounce_delay - (current_time - self._last_action_time)
            # 延后触发更新
            self.hass.helpers.dispatcher.async_dispatcher_send(
                f"{DOMAIN}_switch_update_{self.entity_id}",
                remaining_time
            )
        else:
            # 正常更新状态
            await self.async_schedule_update_ha_state(True)
