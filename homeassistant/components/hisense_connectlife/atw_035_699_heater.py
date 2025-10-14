# atw_035_699_water_heater.py
"""Platform for Hisense ATW 035-699 Water Heater integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
    STATE_ECO,
    STATE_OFF,
    STATE_ELECTRIC,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MIN_TEMP_WATER,
    MAX_TEMP_WATER,
    StatusKey,
    OPERATION_MODE_ECO,
    OPERATION_MODE_VACATION,
)
from .coordinator import HisenseACPluginDataUpdateCoordinator
from .models import DeviceInfo as HisenseDeviceInfo
from .devices import get_device_parser, BaseBeanParser

_LOGGER = logging.getLogger(__name__)

STATE_HEAT = "制热"
STATE_COOL = "制冷"
STATE_AUTO = "自动"
STATE_HOT_WATER_COOL = "热水+制冷"
STATE_HOT_WATER_AUTO = "热水+自动"
STATE_HOT_WATER = "热水"
STATE_HOT_WATER_HEAT = "热水+制热"

OPERATION1_MODE_MAP = {
    "0": STATE_HEAT,
    "1": STATE_COOL,
    "15": STATE_AUTO,
    "5": STATE_HOT_WATER_COOL,
    "16": STATE_HOT_WATER_AUTO,
    "3": STATE_HOT_WATER,
    "6": STATE_HOT_WATER_HEAT,
}
REVERSE_OPERATION_MAP = {v: k for k, v in OPERATION1_MODE_MAP.items()}

async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Hisense ATW 035-699 Water Heater platform."""
    _LOGGER.debug("ATW 035-699 WaterHeater data start")
    coordinator: HisenseACPluginDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    try:
        # Trigger initial data update
        await coordinator.async_config_entry_first_refresh()

        # Get devices from coordinator
        devices = coordinator.data
        if not devices:
            _LOGGER.warning("No devices found in coordinator data")
            return

        _LOGGER.debug("Coordinator ATW 035-699 WaterHeater after refresh: %s", devices)

        entities = [
            Atw035699WaterHeater(coordinator, device)
            for device_id, device in devices.items()
            if isinstance(device, HisenseDeviceInfo) and device.type_code == "035" and device.feature_code == "699"
        ]

        if entities:
            async_add_entities(entities)
        else:
            _LOGGER.warning("No supported ATW 035-699 water heaters found")

    except Exception as err:
        _LOGGER.error("Failed to setup ATW 035-699 water heater platform: %s", err)
        raise

class Atw035699WaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """Hisense ATW 035-699 Water Heater entity implementation."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
            WaterHeaterEntityFeature.TARGET_TEMPERATURE |
            WaterHeaterEntityFeature.OPERATION_MODE |
            WaterHeaterEntityFeature.ON_OFF
    )

    TEMP_RANGE_MAP = {
        "035-699": {
            STATE_HEAT_PUMP: (15, 60),
            STATE_ECO: (15, 60),
            STATE_HIGH_DEMAND: (15, 65),
            "双能2模式": (15, 70),
            STATE_ELECTRIC: (15, 70),
        },
    }

    def __init__(
            self,
            coordinator: HisenseACPluginDataUpdateCoordinator,
            device: HisenseDeviceInfo,
    ) -> None:
        """Initialize the water heater entity."""
        super().__init__(coordinator)
        self._device_id = device.puid
        self._attr_unique_id = f"{device.device_id}_atw_035_699_water_heater"
        self._attr_name = device.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.name,
            manufacturer="Hisense",
            model=f"{device.type_name} ({device.feature_name})",
        )
        _LOGGER.debug("进入ATW 035-699热水器实体: %s", device.feature_name)
        device_type = device.get_device_type()
        if device_type:
            try:
                self._parser = coordinator.api_client.parsers.get(device.device_id)
                _LOGGER.debug("Using parser for device type %s-%s:%s", device_type.type_code, device_type.feature_code,
                              self._parser)
                # 保存 device_type 的 type_code 和 feature_code 供后续使用
                self._current_type_code = device_type.type_code
                self._current_feature_code = device_type.feature_code
                # 初始化设备能力
                self._attr_operation_list = self._get_supported_modes(device)
                # 初始化温度范围
                self._update_temperature_range()
            except Exception as err:
                _LOGGER.error("Failed to get device parser: %s", err)
                self._parser = None
        else:
            self._parser = None

        # Default modes if parser not available
        if not hasattr(self, '_attr_operation_list'):
            self._attr_operation_list = [STATE_OFF, STATE_ECO, STATE_ELECTRIC, STATE_HEAT_PUMP, STATE_HIGH_DEMAND]

        self._attr_min_temp = MIN_TEMP_WATER
        self._attr_max_temp = MAX_TEMP_WATER
        self._attr_target_temperature_step = 1

    def _get_supported_modes(self, device: HisenseDeviceInfo) -> list[str]:
        """获取设备支持的操作模式"""
        modes = [STATE_OFF]
        work_mode_attr = self._parser.attributes.get(StatusKey.MODE)
        if work_mode_attr and work_mode_attr.value_map:
            for key, value in work_mode_attr.value_map.items():
                # Map Chinese descriptions to HA modes
                if "制热" in value or STATE_HEAT in value.lower():
                    modes.append(STATE_HEAT)
                elif "制冷" in value or STATE_COOL in value.lower():
                    modes.append(STATE_COOL)
                elif "自动" in value or STATE_AUTO in value.lower():
                    modes.append(STATE_AUTO)
                elif "热水+制冷" in value or STATE_HOT_WATER_COOL in value.lower():
                    modes.append(STATE_HOT_WATER_COOL)
                elif "热水+自动" in value or STATE_HOT_WATER_AUTO in value.lower():  # 添加双能1模式的支持
                    modes.append(STATE_HOT_WATER_AUTO)
                elif "热水" in value or STATE_HOT_WATER in value.lower():  # 添加双能1模式的支持
                    modes.append(STATE_HOT_WATER)
                elif "热水+制热" in value or STATE_HOT_WATER_HEAT in value.lower():  # 添加双能1模式的支持
                    modes.append(STATE_HOT_WATER_HEAT)

        return modes

    def _update_temperature_range(self):
        """Update the temperature range based on the current mode and feature_code."""
        if not self._parser or not self._current_feature_code:
            return

        current_mode = self.current_operation
        if current_mode in self.TEMP_RANGE_MAP.get(self._current_feature_code, {}):
            min_temp, max_temp = self.TEMP_RANGE_MAP[self._current_feature_code][current_mode]
            self._attr_min_temp = min_temp
            self._attr_max_temp = max_temp
            _LOGGER.debug("Updated temperature range to %d-%d for mode %s and feature_code %s", min_temp, max_temp,
                          current_mode, self._current_feature_code)
        else:
            _LOGGER.warning("No temperature range found for mode %s and feature_code %s", current_mode,
                            self._current_feature_code)

    @property
    def _device(self):
        """获取当前设备数据"""
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        return self._device and self._device.is_online

    @property
    def is_on(self) -> bool:
        """返回热水器是否开启"""
        if not self._device:
            return False
        power_status = self._device.get_status_value(StatusKey.POWER)
        return power_status == "1"

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        try:
            _LOGGER.debug("Turning on device %s", self._device_id)
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
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.POWER: "0"},
            )
        except Exception as err:
            _LOGGER.error("Failed to turn off: %s", err)

    @property
    def current_operation(self) -> str | None:
        """返回当前操作模式"""
        if not self._device:
            return None
        if not self.is_on:
            return STATE_OFF

        hisense_mode = self._device.get_status_value(StatusKey.MODE)
        _LOGGER.debug("hisense_mode %s", hisense_mode)
        ha_mode = OPERATION1_MODE_MAP.get(hisense_mode, STATE_ELECTRIC)
        return ha_mode

    @property
    def current_temperature(self) -> float | None:
        """返回当前水温"""
        if not self._device:
            return None
        temp = self._device.get_status_value(StatusKey.WATER_TANK_TEMP)
        if isinstance(temp, str):
            try:
                return float(temp)
            except ValueError:
                _LOGGER.error("Failed to convert temperature to float: %s", temp)
                return None
        return temp

    @property
    def target_temperature(self) -> float | None:
        """返回目标水温"""
        if not self._device:
            return None
        temp = self._device.get_status_value(StatusKey.TARGET_TEMP)
        if isinstance(temp, str):
            try:
                return float(temp)
            except ValueError:
                _LOGGER.error("Failed to convert target temperature to float: %s", temp)
                return None
        return temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        try:
            await self.coordinator.async_control_device(
                puid=self._device_id,
                properties={StatusKey.TARGET_TEMP: str(int(temperature))},
            )
        except Exception as err:
            _LOGGER.error("Failed to set temperature: %s", err)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """设置工作模式"""
        if operation_mode == STATE_OFF:
            await self.async_turn_off()
            return

        try:
            # Make sure the device is on first
            if not self.is_on:
                await self.async_turn_on()

            # Find the Hisense mode value for this HA mode
            hisense_mode = None

            # Try to map using device parser
            if hasattr(self, '_parser') and self._parser:
                work_mode_attr = self._parser.attributes.get(StatusKey.MODE)
                if work_mode_attr and work_mode_attr.value_map:
                    for key, value in work_mode_attr.value_map.items():
                        if operation_mode == STATE_HEAT and ("制热" in value or STATE_HEAT in value.lower()):
                            hisense_mode = key
                            break
                        elif operation_mode == STATE_COOL and (
                                "制冷" in value or STATE_COOL in value.lower()):
                            hisense_mode = key
                            break
                        elif operation_mode == STATE_AUTO and (
                                "自动" in value or STATE_AUTO in value.lower()):
                            hisense_mode = key
                            break
                        elif operation_mode == STATE_HOT_WATER_COOL and (
                                "热水+制冷" in value or STATE_HOT_WATER_COOL in value.lower()):
                            hisense_mode = key
                            break
                        elif operation_mode == STATE_HOT_WATER_AUTO and (
                                "热水+自动" in value or STATE_HOT_WATER_AUTO in value.lower()):  # 添加双能1模式的支持
                            hisense_mode = key
                            break
                        elif operation_mode == STATE_HOT_WATER and (
                                "热水" in value or STATE_HOT_WATER in value.lower()):  # 添加双能1模式的支持
                            hisense_mode = key
                            break
                        elif operation_mode == STATE_HOT_WATER_HEAT and (
                                "热水+制热" in value or STATE_HOT_WATER_HEAT in value.lower()):  # 添加双能1模式的支持
                            hisense_mode = key
                            break

            # Fallback to standard mapping
            if not hisense_mode:
                mode_str = REVERSE_OPERATION_MAP.get(operation_mode)
                if mode_str:
                    hisense_mode = mode_str

            if hisense_mode:
                _LOGGER.debug("Setting HVAC mode to %s (Hisense value: %s)", operation_mode, hisense_mode)
                await self.coordinator.async_control_device(
                    puid=self._device_id,
                    properties={StatusKey.MODE: hisense_mode},
                )
                # 更新温度范围
                self._update_temperature_range()
                # 刷新实体状态
                self.async_write_ha_state()
            else:
                _LOGGER.error("Could not find Hisense mode value for HA mode: %s", operation_mode)
        except Exception as err:
            _LOGGER.error("Failed to set hvac mode: %s", err)

    async def async_turn_away_mode_on(self) -> None:
        """开启离家模式"""
        try:
            await self.coordinator.set_away_mode(self._device_id, True)
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Enable away mode failed: %s", err)

    async def async_turn_away_mode_off(self) -> None:
        """关闭离家模式"""
        try:
            await self.coordinator.set_away_mode(self._device_id, False)
            self.async_write_ha_state()
        except Exception as err:
            _LOGGER.error("Disable away mode failed: %s", err)
