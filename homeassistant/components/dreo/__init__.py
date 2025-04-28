"""Dreo for Integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import DreoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type DreoConfigEntry = ConfigEntry[DreoData]

PLATFORMS = [Platform.FAN]
SYNC_INTERVAL = timedelta(seconds=10)  # Device synchronization interval


@dataclass
class DreoData:
    """Dreo Data."""

    client: HsCloud
    devices: list[dict[str, Any]]
    coordinators: dict[str, DreoDataUpdateCoordinator]


async def async_login(hass: HomeAssistant, username: str, password: str) -> DreoData:
    """Log into Dreo and return client and device data."""
    client = HsCloud(username, password)

    def setup_client():
        client.login()
        return client.get_devices()

    try:
        devices = await hass.async_add_executor_job(setup_client)
    except HsCloudBusinessException as ex:
        raise ConfigEntryNotReady("invalid username or password") from ex

    return DreoData(client, devices, {})


async def async_setup_entry(hass: HomeAssistant, config_entry: DreoConfigEntry) -> bool:
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    # Login and get device data
    config_entry.runtime_data = await async_login(hass, username, password)

    # Set up coordinators for each device
    await async_setup_devices(hass, config_entry)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def _async_sync_wrapper(now=None):
        """Wrap the device synchronization function and call it."""
        # 安全检查
        if (
            hasattr(config_entry, "runtime_data")
            and config_entry.runtime_data is not None
        ):
            await async_sync_devices(hass, config_entry)
        else:
            _LOGGER.warning("Runtime data missing, skipping sync")

    # 正确注册定时任务，确保在卸载时清理
    config_entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_sync_wrapper,
            SYNC_INTERVAL,
        )
    )

    return True


async def async_setup_devices(
    hass: HomeAssistant, config_entry: DreoConfigEntry
) -> None:
    """Set up coordinators for all devices."""

    for device in config_entry.runtime_data.devices:
        await async_setup_device(hass, config_entry, device)


async def async_setup_device(
    hass: HomeAssistant, config_entry: DreoConfigEntry, device: dict[str, Any]
) -> None:
    """Set up coordinator for a single device."""

    device_model = device.get("model")
    device_id = str(device.get("deviceSn", ""))

    if not device_id:
        return

    # Skip if device already has a coordinator
    if device_id in config_entry.runtime_data.coordinators:
        return

    # Create device coordinator
    coordinator = DreoDataUpdateCoordinator(
        hass, config_entry.runtime_data.client, device_id, device_model or ""
    )

    # Initial data refresh
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    config_entry.runtime_data.coordinators[device_id] = coordinator


async def async_sync_devices(
    hass: HomeAssistant, config_entry: DreoConfigEntry
) -> None:
    """Synchronize cloud devices with local devices."""

    try:
        if config_entry is None:
            _LOGGER.warning("Config entry not available, skipping device sync")
            return

        client = config_entry.runtime_data.client
        # 获取最新设备列表
        cloud_devices = await hass.async_add_executor_job(client.get_devices)

        # 获取当前设备ID和云端设备ID
        current_device_ids = set(config_entry.runtime_data.coordinators.keys())
        cloud_device_ids = {
            str(device.get("deviceSn", ""))
            for device in cloud_devices
            if device.get("deviceSn")
        }

        # 处理设备变更
        new_device_ids = cloud_device_ids - current_device_ids
        removed_device_ids = current_device_ids - cloud_device_ids

        # 添加新设备
        for device in cloud_devices:
            device_id = str(device.get("deviceSn", ""))
            if device_id in new_device_ids:
                _LOGGER.info("New device added: %s", device_id)
                await async_setup_device(hass, config_entry, device)

        # 移除旧设备
        for device_id in removed_device_ids:
            if device_id in config_entry.runtime_data.coordinators:
                _LOGGER.info("Device removed: %s", device_id)
                del config_entry.runtime_data.coordinators[device_id]

        # 清理实体注册表 - 简化版
        entity_registry = er.async_get(hass)
        removed_entities = 0

        # 直接在一次循环中查找和移除实体
        for entity in list(entity_registry.entities.values()):
            if entity.config_entry_id != config_entry.entry_id:
                continue

            # 从unique_id中提取设备ID
            unique_id = entity.unique_id
            device_id = unique_id.split("_")[0] if "_" in unique_id else unique_id

            if device_id not in cloud_device_ids:
                entity_registry.async_remove(entity.entity_id)
                removed_entities += 1

        # 清理设备注册表
        if removed_device_ids:
            device_registry = dr.async_get(hass)
            for removed_device_id in removed_device_ids:
                # 查找设备注册表中的匹配设备
                device_entries = [
                    dev
                    for dev in device_registry.devices.values()
                    if dev.config_entries == {config_entry.entry_id}
                    and any(ident[1] == removed_device_id for ident in dev.identifiers)
                ]

                # 移除找到的设备
                for device_entry in device_entries:
                    device_registry.async_remove_device(device_entry.id)

        # 更新设备列表
        config_entry.runtime_data.devices = cloud_devices

        if new_device_ids:
            for platform in PLATFORMS:
                await hass.config_entries.async_forward_entry_unload(
                    config_entry, platform
                )
                await hass.config_entries.async_forward_entry_setup(
                    config_entry, platform
                )

        _LOGGER.info(
            "同步完成: %d个设备 (%d个新增, %d个移除, %d个实体已清理)",
            len(cloud_devices),
            len(new_device_ids),
            len(removed_device_ids),
            removed_entities,
        )
    except Exception as ex:
        _LOGGER.exception("设备同步出错: %s", ex)  # noqa: TRY401


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
