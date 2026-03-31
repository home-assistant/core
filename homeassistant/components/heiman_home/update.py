"""Update platform for Heiman integration."""

from __future__ import annotations

import logging
from typing import Any

# Simple version comparison (assumes semantic versioning)
from packaging import version

from heimanconnect import HeimanDevice

from homeassistant import config_entries
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heiman update entities based on a config entry."""
    coordinator: HeimanDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    devices = coordinator.get_all_devices()
    update_entities = []
    
    for device in devices:
        # 为每个设备添加更新实体（即使没有固件版本也会创建，用于显示状态）
        update_entities.append(
            HeimanUpdateEntity(
                coordinator=coordinator,
                device=device,
            )
        )
    
    async_add_entities(update_entities)


class HeimanUpdateEntity(CoordinatorEntity[HeimanDataUpdateCoordinator], UpdateEntity):
    """Representation of a Heiman update entity."""

    _attr_has_entity_name = True
    _attr_supported_features = UpdateEntityFeature.INSTALL | UpdateEntityFeature.SPECIFIC_VERSION

    def __init__(
        self,
        coordinator: HeimanDataUpdateCoordinator,
        device: HeimanDevice,
    ) -> None:
        """Initialize the update entity.
        
        Args:
            coordinator: Data coordinator
            device: Heiman device
        """
        super().__init__(coordinator)
        self._device = device
        
        # 生成唯一 ID
        self._attr_unique_id = f"{device.device_id}_firmware_update"
        
        # 设置名称
        self._attr_name = "Firmware Info"
        
        # 提取固件版本 - 使用多重策略
        sw_version = self._extract_firmware_version(device)
        
        # 获取设备信息
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer=device.manufacturer,
            model=device.model or device.product_id,
            sw_version=sw_version,
            hw_version=device.hardware_version,
        )
        
        # 初始化版本属性
        self._attr_installed_version = sw_version
        self._attr_latest_version = sw_version  # 默认使用当前版本
        self._attr_release_summary = None
        self._attr_release_url = None
        self._attr_title = "Heiman Firmware"
        self._attr_in_progress = False
        self._attr_update_percentage = None
        self._attr_auto_update = False
        
        _LOGGER.debug(
            "Initialized update entity for device %s with firmware version: %s",
            device.device_name,
            sw_version or "None",
        )
    
    def _extract_firmware_version(self, device: HeimanDevice) -> str | None:
        """Extract firmware version from device using multiple strategies.
        
        Args:
            device: Heiman device
            
        Returns:
            Firmware version string or None
        """
        sw_version = None
        
        # 策略 1: 直接从设备的 firmware_version 属性获取
        if hasattr(device, 'firmware_version') and device.firmware_version:
            sw_version = device.firmware_version
            _LOGGER.debug(
                "Got firmware version %s for device %s from device.firmware_version",
                sw_version,
                device.device_id,
            )
            return sw_version
        
        # 策略 2: 从 raw_data.firmwareInfo.version 获取
        if hasattr(device, 'raw_data') and device.raw_data:
            firmware_info = device.raw_data.get("firmwareInfo", {})
            if isinstance(firmware_info, dict) and firmware_info.get("version"):
                sw_version = firmware_info.get("version")
                _LOGGER.debug(
                    "Extracted firmware version %s for device %s from raw_data.firmwareInfo",
                    sw_version,
                    device.device_id,
                )
                return sw_version
        
        # 策略 3: 从 firmware_info.version 获取
        if hasattr(device, 'firmware_info') and device.firmware_info:
            if isinstance(device.firmware_info, dict) and device.firmware_info.get("version"):
                sw_version = device.firmware_info.get("version")
                _LOGGER.debug(
                    "Extracted firmware version %s for device %s from firmware_info",
                    sw_version,
                    device.device_id,
                )
                return sw_version
        
        # 没有找到固件版本
        if sw_version is None:
            _LOGGER.debug(
                "No firmware version found for device %s (%s)",
                device.device_id,
                device.device_name,
            )
        
        return sw_version
    
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
    def installed_version(self) -> str | None:
        """Return the current installed firmware version."""
        # 优先返回缓存的版本
        if self._attr_installed_version:
            return self._attr_installed_version
        
        # 回退到动态获取
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return None
        
        return self._extract_firmware_version(device)
    
    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version.
        
        For now, we don't have a way to check for new firmware versions via API.
        This should be implemented when the API supports firmware update checks.
        """
        # 优先返回缓存的最新版本
        if self._attr_latest_version:
            return self._attr_latest_version
        
        # 回退到安装的版本（表示没有可用更新）
        return self.installed_version
    
    def _update_from_cache(self) -> bool:
        """Update entity state from coordinator cache (synchronous).
        
        Returns True if state was updated from cache, False if cache miss.
        """
        device = self.coordinator.get_device(self._device.device_id)
        if not device:
            return False
        
        # 获取安装的版本
        installed_version = self._extract_firmware_version(device)
        if installed_version:
            # 只有在没有更好的版本时才更新
            if (
                not self._attr_installed_version
                or self._attr_installed_version == "unknown"
            ):
                self._attr_installed_version = installed_version
                _LOGGER.debug(
                    "Update entity %s set installed version: %s",
                    self._attr_name,
                    installed_version,
                )
        
        # 尝试从协调器获取最新版本（如果将来支持）
        # TODO: 当 API 支持固件更新检查时实现
        # if self.coordinator and hasattr(self.coordinator, "get_device_property"):
        #     latest_version = self.coordinator.get_device_property(
        #         self._device.device_id,
        #         "LatestFirmwareVersion",
        #     )
        #     if latest_version:
        #         latest_ver_str = str(latest_version)
        #         self._attr_latest_version = latest_ver_str
        #         _LOGGER.debug(
        #             "Update entity %s got latest version from cache: %s",
        #             self._attr_name,
        #             latest_ver_str,
        #         )
        
        # 如果没有最新版本，使用安装版本
        if installed_version and not self._attr_latest_version:
            self._attr_latest_version = installed_version
        
        # 记录当前状态用于调试
        _LOGGER.debug(
            "Update entity %s state: installed=%s, latest=%s",
            self._attr_name,
            self._attr_installed_version,
            self._attr_latest_version,
        )
        
        return True
    
    def _version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        try:
            return version.parse(str(latest_version)) > version.parse(
                str(installed_version),
            )
        except ImportError:
            # Fallback to simple string comparison if packaging is not available
            return str(latest_version) != str(installed_version)
        except Exception:
            _LOGGER.exception(
                "Error comparing versions %s and %s",
                latest_version,
                installed_version,
            )
            return False
    
    @property
    def release_summary(self) -> str | None:
        """Return summary of the latest release."""
        # TODO: Implement when API supports firmware update information
        return None
    
    @property
    def in_progress(self) -> bool:
        """Return whether an update is currently in progress."""
        # Check if there's a property indicating update status
        device = self.coordinator.get_device(self._device.device_id)
        if device:
            update_prop = device.properties.get("firmware_update_status")
            if update_prop and update_prop.value:
                return str(update_prop.value).lower() in ["updating", "downloading", "installing"]
        return False
    
    async def async_update(self) -> None:
        """Update the entity state from coordinator cache (polling).
        
        This is called during polling by Home Assistant.
        Note: HA automatically calls async_write_ha_state() after async_update().
        """
        try:
            self._update_from_cache()
        except Exception:
            _LOGGER.exception("Error updating firmware info for %s", self._attr_name)
    
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator (MQTT push).
        
        This is called when the coordinator has new data (e.g., from MQTT).
        Updates entity state immediately without waiting for next poll.
        """
        try:
            if self._update_from_cache():
                _LOGGER.debug(
                    "Update entity %s received coordinator update (MQTT)",
                    self._attr_name,
                )
                # Write the new state to Home Assistant immediately
                self.async_write_ha_state()
        except Exception:
            _LOGGER.exception("Error updating firmware info for %s", self._attr_name)
    
    async def async_install(
        self,
        version: str | None = None,
        backup: bool = False,
        **kwargs: Any,
    ) -> None:
        """Install a firmware update.
        
        Args:
            version: Version to install (latest if None)
            backup: Whether to create a backup before installing
            **kwargs: Additional arguments
            
        Raises:
            NotImplementedError: If firmware update is not supported via API
        """
        # TODO: Implement firmware update when API supports it
        # This would typically call:
        # await self.coordinator.api_client.async_control_device(
        #     device_id=self._device.device_id,
        #     property_identifier="firmware_update",
        #     value="start",
        # )
        
        _LOGGER.warning(
            "Firmware update is not yet supported for device %s via API",
            self._device.device_name,
        )
        raise NotImplementedError(
            "Firmware update is not yet supported for this device"
        )
