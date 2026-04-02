"""Heiman Home Assistant integration."""

from __future__ import annotations

import logging
from pathlib import Path
import sys

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .api import HeimanApiClient
from .const import (
    AREA_NAME_RULE_HOME_ROOM,
    CONF_AREA_NAME_RULE,
    CONF_DEVICE_FILTER_MODE,
    CONF_DEVICE_LIST,
    CONF_MODEL_FILTER_MODE,
    CONF_MODEL_LIST,
    CONF_ROOM_FILTER_MODE,
    CONF_ROOM_LIST,
    CONF_STATISTICS_LOGIC,
    CONF_TYPE_FILTER_MODE,
    CONF_TYPE_LIST,
    DOMAIN,
    PLATFORMS,
    SERVICE_READ_DEVICE_PROPERTIES,
)
from .coordinator import HeimanDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

try:
    from heimanconnect import DeviceManagement
except ModuleNotFoundError:
    custom_components_path = Path("/config/custom_components")
    if str(custom_components_path) not in sys.path:
        sys.path.insert(0, str(custom_components_path))
        _LOGGER.info("Added custom components path: %s", custom_components_path)
    from heimanconnect import DeviceManagement

type HeimanConfigEntry = ConfigEntry[HeimanDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Set up Heiman from a config entry."""
    # 检查配置中是否包含 token
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed("Config entry missing token")

    try:
        implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err

    session = OAuth2Session(hass, entry, implementation)

    # 验证 token 有效性
    try:
        await session.async_ensure_token_valid()
    except OAuth2TokenRequestReauthError as err:
        raise ConfigEntryAuthFailed from err
    except OAuth2TokenRequestError as err:
        raise ConfigEntryNotReady from err

    # 创建 API 客户端
    api_client = HeimanApiClient(hass=hass, session=session)

    # 测试 API 连接
    try:
        user_info = await api_client.async_get_user_info()
        _LOGGER.debug("Successfully authenticated as user: %s", user_info.email)
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Heiman API: {err}") from err

    # 初始化设备管理
    device_management = DeviceManagement()

    # 配置设备过滤
    filter_config = {
        "filter_mode": entry.data.get(CONF_DEVICE_FILTER_MODE, "exclude"),
        "statistics_logic": entry.data.get(CONF_STATISTICS_LOGIC, "or"),
        "room_filter_mode": entry.data.get(CONF_ROOM_FILTER_MODE, "exclude"),
        "room_list": entry.data.get(CONF_ROOM_LIST, []),
        "type_filter_mode": entry.data.get(CONF_TYPE_FILTER_MODE, "exclude"),
        "type_list": entry.data.get(CONF_TYPE_LIST, []),
        "model_filter_mode": entry.data.get(CONF_MODEL_FILTER_MODE, "exclude"),
        "model_list": entry.data.get(CONF_MODEL_LIST, []),
        "device_filter_mode": entry.data.get(CONF_DEVICE_FILTER_MODE, "exclude"),
        "device_list": entry.data.get(CONF_DEVICE_LIST, []),
    }

    # 配置区域同步
    area_sync_mode = entry.data.get(CONF_AREA_NAME_RULE, AREA_NAME_RULE_HOME_ROOM)

    device_management.configure(
        filter_config=filter_config,
        area_sync_mode=area_sync_mode,
    )

    # 存储设备管理到 hass.data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {
        "device_management": device_management,
    }

    # 创建数据协调器
    coordinator = HeimanDataUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        api_client=api_client,
        config_entry=entry,
        device_management=device_management,
        oauth_session=session,  # Pass OAuth2 session for MQTT token retrieval
    )

    # 首次更新数据
    await coordinator.async_config_entry_first_refresh()

    # 初始化 MQTT 客户端（用于实时设备属性更新）
    await coordinator.async_init_mqtt_client()

    # 存储协调器到 hass.data 和 runtime_data
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    # 加载平台
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 注册服务来读取设备属性
    async def handle_read_device_properties(call):
        """Handle read device properties service call."""
        device_id = call.data.get("device_id")
        if not device_id:
            _LOGGER.error("Device ID is required for read_device_properties service")
            return

        coordinator: HeimanDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_read_device_properties(device_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_READ_DEVICE_PROPERTIES,
        handle_read_device_properties,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(_hass: HomeAssistant, entry: HeimanConfigEntry) -> bool:
    """Migrate old configuration entries."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    # 未来可以在这里添加迁移逻辑

    return True
