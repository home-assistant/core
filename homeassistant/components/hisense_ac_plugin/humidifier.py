"""Platform for Hisense Dehumidifier integration."""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timedelta

from homeassistant.components.humidifier import (
    HumidifierEntity,
    HumidifierEntityFeature,
    HumidifierDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    StatusKey,
)
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .models import DeviceInfo as HisenseDeviceInfo

_LOGGER = logging.getLogger(__name__)

# 定义操作模式映射
STATE_CONTINUOUS = "STATE_CONTINUOUS"
STATE_NORMAL = "STATE_NORMAL"
STATE_AUTO = "STATE_AUTO"
STATE_DRY = "STATE_DRY"
STATE_OFF = "STATE_OFF"

OPERATION_DEHUMIDIFIER_MAP = {
    "0": STATE_CONTINUOUS,
    "1": STATE_NORMAL,
    "2": STATE_AUTO,
    "3": STATE_DRY,
}
REVERSE_OPERATION_DEHUMIDIFIER_MAP = {v: k for k, v in OPERATION_DEHUMIDIFIER_MAP.items()}

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense Dehumidifier platform."""
    _LOGGER.debug("Dehumidifier data start")
    coordinator: HisenseACPluginDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    try:
        # Trigger initial data update
        await coordinator.async_config_entry_first_refresh()

        # Get devices from coordinator
        devices = coordinator.data
        if not devices:
            _LOGGER.warning("No devices found in coordinator data")
            return

        _LOGGER.debug("Coordinator dehumidifier after refresh: %s", devices)
        entities = []
        for device_id, device in devices.items():
            _LOGGER.debug("Processing 除湿机: %s", device.to_dict())
            if isinstance(device, HisenseDeviceInfo) and device.is_humidityr():
                _LOGGER.info(
                    "Adding dehumidifier entity for device: %s (type: %s-%s)",
                    device.name,
                    device.type_code,
                    device.feature_code
                )
                entity = HisenseDehumidifier(coordinator, device)
                entities.append(entity)
            else:
                _LOGGER.warning(
                    "Skipping unsupported device: %s-%s (%s)",
                    getattr(device, 'type_code', None),
                    getattr(device, 'feature_code', None),
                    getattr(device, 'name', None)
                )
        if entities:
            async_add_entities(entities)
        else:
            _LOGGER.warning("No supported dehumidifiers found")

    except Exception as err:
        _LOGGER.error("Failed to setup dehumidifier platform: %s", err)
        raise

class HisenseDehumidifier(CoordinatorEntity, HumidifierEntity):
    """Hisense Dehumidifier entity implementation."""

    _attr_has_entity_name = False
    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_target_humidity_step = 5  # 修改步长为5
    _attr_device_class = HumidifierDeviceClass.DEHUMIDIFIER  # 设置为除湿器

    def __init__(
            self,
            coordinator: HisenseACPluginDataUpdateCoordinator,
            device: HisenseDeviceInfo,
    ) -> None:
        """Initialize the dehumidifier entity."""
        super().__init__(coordinator)
        self.static_data = coordinator.api_client.static_data.get(device.device_id)
        self._device_id = device.puid
        self._attr_unique_id = f"{device.device_id}_dehumidifier"
        self._attr_name = device.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Hisense",
            model=f"{device.type_name} ({device.feature_name})",
        )
        _LOGGER.debug("z: %s", device.feature_name)
        device_type = device.get_device_type()
        if device_type:
            try:
                self._parser = coordinator.api_client.parsers.get(device.device_id)
                _LOGGER.debug("Using parser for device type %s-%s:%s", device_type.type_code, device_type.feature_code,
                              self._parser.attributes)
                # 保存 device_type 的 type_code 和 feature_code 供后续使用
                self._current_type_code = device_type.type_code
                self._current_feature_code = device_type.feature_code
                # 初始化设备能力
                self._attr_available_modes = self._get_supported_modes(device)
            except Exception as err:
                _LOGGER.error("Failed to get device parser: %s", err)
                self._parser = None
        else:
            self._parser = None

        # Default modes if parser not available
        if not hasattr(self, '_attr_available_modes'):
            self._attr_available_modes = [STATE_CONTINUOUS, STATE_NORMAL, STATE_AUTO, STATE_DRY]

        # 获取目标湿度范围
        target_humidity_attr = self._parser.attributes.get(StatusKey.HUMIDITY) if self._parser else None

        # 解析 propertyValueList 以获取湿度范围
        def parse_humidity_range(property_value_list):
            ranges = []
            for item in property_value_list.split(','):
                item = item.strip()
                if '~' in item:
                    lower, upper = map(int, item.split('~'))
                    ranges.append((lower, upper))
            return ranges

        # 获取解析后的湿度范围
        if target_humidity_attr and target_humidity_attr.value_range:
            humidity_ranges = parse_humidity_range(target_humidity_attr.value_range)
            # 使用第一个范围作为默认范围
            if humidity_ranges:
                self._attr_min_humidity, self._attr_max_humidity = humidity_ranges[0]
            else:
                _LOGGER.warning("No valid humidity range found, using default range.")
                self._attr_min_humidity = 30
                self._attr_max_humidity = 80
        else:
            _LOGGER.warning("Target humidity attribute or value range not found, using default range.")
            self._attr_min_humidity = 30
            self._attr_max_humidity = 80

        self._attr_target_humidity_step = 5  # 修改步长为5

        # 添加防跳变相关属性
        self._last_manual_control_time = None
        self._last_cloud_state = None
        self._debounce_time = timedelta(seconds=5)
        self._last_cloud_state_mode = None
        self._pending_mode = None
        self._is_manual_control = False  # 添加手动控制标志

    def _get_supported_modes(self, device: HisenseDeviceInfo) -> list[str]:
        """获取设备支持的模式"""
        _LOGGER.debug("当前除湿机的102-64属性 %s-%s:%s", device.type_code, device.feature_code,
                      self.static_data)
        Mode_settings_persistent = '1'
        Mode_settings_normal = '1'
        Mode_settings_auto = '1'
        Mode_settings_dry = '1'
        if self.static_data:
            Mode_settings_persistent = self.static_data.get("Mode_settings_persistent")
            Mode_settings_normal = self.static_data.get("Mode_settings_normal")
            Mode_settings_auto = self.static_data.get("Mode_settings_auto")
            Mode_settings_dry = self.static_data.get("Mode_settings_dry")
        modes = []
        work_mode_attr = self._parser.attributes.get(StatusKey.MODE)
        if work_mode_attr and work_mode_attr.value_map:
            for key, value in work_mode_attr.value_map.items():
                # Map Chinese descriptions to HA modes
                if "持续" in value or "continuous" in value.lower():
                    if Mode_settings_persistent == '1':
                        modes.append(STATE_CONTINUOUS)
                elif "正常" in value or "normal" in value.lower():
                    if Mode_settings_normal == '1':
                        modes.append(STATE_NORMAL)
                elif "自动" in value or "auto" in value.lower():
                    if Mode_settings_auto == '1':
                        modes.append(STATE_AUTO)
                elif "干衣" in value or "dry" in value.lower():
                    if Mode_settings_dry == '1':
                        modes.append(STATE_DRY)
            _LOGGER.debug(" 除湿机添加完成的模式 %s-%s:%s", device.type_code, device.feature_code,
                      modes)
        return modes

    @property
    def _device(self):
        """获取当前设备数据"""
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        # return True
        #水箱故障触发时禁用当前除湿机
        if 'f_e_waterfull' in self._device.failed_data:
            return False
        return self._device and self._device.is_online

    @property
    def is_on(self) -> bool:
        """返回湿度控制是否开启"""
        if not self._device:
            return False
        
        # 检查是否在防跳变时间内
        if self._last_manual_control_time and datetime.now() - self._last_manual_control_time < self._debounce_time:
            return self._last_cloud_state if self._last_cloud_state is not None else False
            
        power_status = self._device.get_status_value(StatusKey.POWER)
        self._last_cloud_state = power_status == "1"
        return self._last_cloud_state

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        try:
            _LOGGER.debug("Turning on device %s", self._device_id)
            self._last_manual_control_time = datetime.now()
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.POWER: "1"},
            )
        except Exception as err:
            _LOGGER.error("Failed to turn on: %s", err)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        try:
            _LOGGER.debug("Turning off device %s", self._device_id)
            self._last_manual_control_time = datetime.now()
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.POWER: "0"},
            )
        except Exception as err:
            _LOGGER.error("Failed to turn off: %s", err)

    @property
    def current_humidity(self) -> int | None:
        """返回当前湿度"""
        if not self._device:
            return None
        humidity = self._device.get_status_value(StatusKey.FHUMIDITY)
        if isinstance(humidity, str):
            try:
                return int(humidity)
            except ValueError:
                _LOGGER.error("Failed to convert humidity to integer: %s", humidity)
                return None
        return humidity

    @property
    def target_humidity(self) -> int | None:
        """返回目标湿度（自动模式强制显示50%）"""
        if not self._device:
            return None

        current_mode = self.mode  # 获取当前模式
        if current_mode == self._get_translation(STATE_AUTO):  # 自动模式强制返回50
            return 50

        # 检查是否在防跳变时间内
        if self._last_manual_control_time and datetime.now() - self._last_manual_control_time < self._debounce_time:
            return self._last_cloud_state if self._last_cloud_state is not None else None

        humidity = self._device.get_status_value(StatusKey.HUMIDITY)
        if isinstance(humidity, str):
            try:
                humidity = int(humidity)
                self._last_cloud_state = humidity
                return humidity
            except ValueError:
                _LOGGER.error("Failed to convert target humidity to integer: %s", humidity)
                return None
        return humidity

    async def async_set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        try:
            current_humidity = self.target_humidity  # 获取当前的目标湿度值

            if current_humidity is None:
                _LOGGER.error("Current humidity value is not available.")
                return

            # Ensure the humidity is within the valid range initially
            if humidity < self._attr_min_humidity or humidity > self._attr_max_humidity:
                _LOGGER.error("Humidity out of range: %s", humidity)
                return

            # Calculate the adjusted humidity value based on the remainder when divided by 5
            remainder = humidity % 5
            if remainder != 0:
                if humidity > current_humidity:
                    # If the new humidity is greater than the current humidity, round up to the next multiple of 5
                    humidity += (5 - remainder)
                else:
                    # If the new humidity is less than the current humidity, round down to the nearest multiple of 5
                    humidity -= remainder

            # Ensure the adjusted humidity is still within the valid range
            if humidity < self._attr_min_humidity:
                humidity = self._attr_min_humidity
            elif humidity > self._attr_max_humidity:
                humidity = self._attr_max_humidity

            self._last_manual_control_time = datetime.now()
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.HUMIDITY: str(humidity)},
            )
        except Exception as err:
            _LOGGER.error("Failed to set humidity: %s", err)

    @property
    def mode(self) -> str | None:
        """返回当前设备的模式，并处理防跳变逻辑"""
        if not self._device:
            return None

        now = datetime.now()
        is_debouncing = False
        if self._last_manual_control_time:
            is_debouncing = (now - self._last_manual_control_time) < self._debounce_time

        _LOGGER.debug(
            "获取模式 - 当前时间: %s - 上次操作: %s - 防跳变窗口: %s - 是否防跳变: %s - 待处理模式: %s - 手动控制: %s",
            now,
            self._last_manual_control_time,
            self._debounce_time,
            is_debouncing,
            self._pending_mode,
            self._is_manual_control
        )

        # 如果是手动控制且在防跳变时间内，直接返回待处理模式
        if self._is_manual_control and is_debouncing:
            return self._pending_mode

        # 获取云端状态
        hisense_mode = self._device.get_status_value(StatusKey.MODE)
        mode_key = OPERATION_DEHUMIDIFIER_MAP.get(hisense_mode, STATE_NORMAL)
        translated_mode = self._get_translation(mode_key)

        # 更新云端状态
        if not self._is_manual_control or not is_debouncing:
            if self._last_cloud_state_mode != translated_mode:
                self._last_cloud_state_mode = translated_mode
                self._pending_mode = translated_mode
                _LOGGER.debug("更新云端模式: %s", translated_mode)

        # 在防跳变期间，始终返回待处理模式
        if is_debouncing and self._pending_mode is not None:
            return self._pending_mode

        return translated_mode

    def _get_translation(self, key: str) -> str:
        current_lang = self.hass.config.language
        translations = self.hass.data.get(f"{DOMAIN}.translations", {}).get(current_lang, {})
        mode = translations.get(key, key)
        return mode

    async def async_set_mode(self, mode: str) -> None:
        if mode == self._get_translation(STATE_OFF):
            await self.async_turn_off()
            return

        try:
            current_lang = self.hass.config.language
            translations = self.hass.data[f"{DOMAIN}.translations"][current_lang]
            key = None
            for k, v in translations.items():
                if v == mode:
                    key = k
                    break
            if not key:
                _LOGGER.error(f"无法找到对应的模式键名：{mode}")
                return

            hisense_mode = REVERSE_OPERATION_DEHUMIDIFIER_MAP.get(key)
            if hisense_mode:
                self._last_manual_control_time = datetime.now()
                self._pending_mode = mode
                self._is_manual_control = True  # 设置手动控制标志
                _LOGGER.debug("设置模式 - 时间: %s - 模式: %s", self._last_manual_control_time, mode)
                
                # 立即更新UI状态
                self.async_write_ha_state()
                
                await self.coordinator.async_control_device(
                    puid=self._device_id,
                    properties={StatusKey.MODE: hisense_mode},
                )
                
                # 启动一个任务来清除手动控制状态
                async def clear_manual_control():
                    await asyncio.sleep(self._debounce_time.total_seconds())
                    self._is_manual_control = False
                    # 获取最新的云端状态
                    hisense_mode = self._device.get_status_value(StatusKey.MODE)
                    mode_key = OPERATION_DEHUMIDIFIER_MAP.get(hisense_mode, STATE_NORMAL)
                    translated_mode = self._get_translation(mode_key)
                    self._pending_mode = translated_mode
                    self._last_cloud_state_mode = translated_mode
                    self.async_write_ha_state()
                
                self.hass.async_create_task(clear_manual_control())
            else:
                _LOGGER.error(f"无法找到 Hisense 对应值：{key}")
        except Exception as err:
            _LOGGER.error(f"设置模式失败：{err}")
            self._is_manual_control = False
            self._pending_mode = None

    @property
    def available_modes(self) -> list[str]:
        translated_modes = [self._get_translation(mode_key) for mode_key in self._attr_available_modes]
        return translated_modes
