"""Data update coordinator for Heiman integration."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from heimanconnect import (
    DeviceManagement,
    HeimanDevice,
    HeimanHome,
    HeimanUser,
    HeimanMqttClient,
    HeimanMQTTError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeimanApiClient
from .const import CONF_HOME_ID, CONF_USER_ID, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class HeimanData:
    """Container for Heiman data."""

    user_info: HeimanUser | None = None
    home_info: HeimanHome | None = None
    devices: dict[str, HeimanDevice] = field(default_factory=dict)
    last_update: datetime | None = None
    errors: dict[str, str] = field(default_factory=dict)


class HeimanDataUpdateCoordinator(DataUpdateCoordinator[HeimanData]):
    """Heiman data update coordinator."""

    config_entry: ConfigEntry

    def __init__(
            self,
            hass: HomeAssistant,
            logger: logging.Logger,
            api_client: HeimanApiClient,
            config_entry: ConfigEntry,
            device_management: DeviceManagement | None = None,
            oauth_session=None,
    ) -> None:
        """Initialize the coordinator.
        
        Args:
            hass: Home Assistant instance
            logger: Logger instance
            api_client: API client instance
            config_entry: Config entry instance
            device_management: Device management instance
            oauth_session: OAuth2 session for token retrieval
        """
        super().__init__(
            hass=hass,
            logger=logger,
            name="Heiman Home",
            update_interval=None,  # Disabled automatic refresh
        )

        self.api_client = api_client
        self.config_entry = config_entry
        self.device_management = device_management
        self.data = HeimanData()
        self.mqtt_client: HeimanMqttClient | None = None
        self.oauth_session = oauth_session

    async def _async_update_data(self) -> HeimanData:
        """Fetch data from Heiman API.
        
        Returns:
            HeimanData object with updated information
            
        Raises:
            ConfigEntryAuthFailed: If authentication fails
            UpdateFailed: If data fetch fails
        """
        try:
            # 获取家庭 ID
            home_id = self.config_entry.data.get(CONF_HOME_ID)
            if not home_id:
                raise UpdateFailed("Home ID not found in config entry")

            # 获取用户信息（只在首次更新时获取）
            if self.data.user_info is None:
                try:
                    self.data.user_info = await self.api_client.async_get_user_info()
                except ConfigEntryAuthFailed:
                    raise
                except Exception as err:
                    _LOGGER.warning("Failed to fetch user info: %s", err)
                    self.data.errors["user_info"] = str(err)

            # 获取家庭信息（只在首次更新时获取）
            if self.data.home_info is None:
                try:
                    homes = await self.api_client.async_get_homes()
                    if homes:
                        self.data.home_info = next(
                            (h for h in homes if h.home_id == home_id),
                            homes[0],
                        )
                except ConfigEntryAuthFailed:
                    raise
                except Exception as err:
                    _LOGGER.warning("Failed to fetch home info: %s", err)
                    self.data.errors["home_info"] = str(err)

            # 获取设备列表和详情
            try:
                devices_dict = await self.api_client.async_get_devices(home_id=home_id)

                # 应用设备过滤
                if self.device_management:
                    devices_list = list(devices_dict.values())
                    filtered_devices_list = (
                        self.device_management.filter_manager.get_filtered_devices(
                            devices_list
                        )
                    )
                    # 转回字典
                    devices = {d.device_id: d for d in filtered_devices_list}
                else:
                    devices = devices_dict

                # 从设备列表中提取固件版本信息
                for device_id, device in devices.items():
                    # 首先检查设备的原始数据中是否有 firmwareInfo
                    if hasattr(device, 'raw_data') and device.raw_data:
                        firmware_info = device.raw_data.get("firmwareInfo", {})
                        if isinstance(firmware_info, dict) and "version" in firmware_info:
                            device.firmware_version = firmware_info.get("version")

                    # 尝试从设备的 firmware_info 属性获取固件版本
                    if hasattr(device, 'firmware_info') and device.firmware_info:
                        if isinstance(device.firmware_info, dict) and "version" in device.firmware_info:
                            # 将固件版本存储到设备对象中供后续使用
                            device.firmware_version = device.firmware_info.get("version")

                # 为过滤后的设备获取详细信息以填充属性值
                for device_id, device in devices.items():
                    try:
                        # 通过 cloud_client 获取设备详情
                        if hasattr(self.api_client, '_cloud_client') and self.api_client._cloud_client:
                            device_detail = await self.api_client._cloud_client._async_get_device_detail(device_id)
                            if device_detail:

                                # 从 firmwareInfo 中提取固件版本（如果之前没有获取到）
                                if not device.firmware_version:
                                    firmware_info = device_detail.get("firmwareInfo", {})
                                    if isinstance(firmware_info, dict) and "version" in firmware_info:
                                        device.firmware_version = firmware_info.get("version")

                                # 从 deriveMetadata 中提取属性值并更新到设备对象
                                if "deriveMetadata" in device_detail:
                                    try:
                                        metadata_str = device_detail.get("deriveMetadata", "")
                                        if metadata_str:
                                            # deriveMetadata is a JSON string that parses to a list of property objects
                                            metadata_list = json.loads(metadata_str)

                                            # Iterate through the list and update properties
                                            if isinstance(metadata_list, list):
                                                for prop_item in metadata_list:
                                                    prop_id = prop_item.get("property", "")
                                                    prop_value = prop_item.get("value")

                                                    # Also check 'id' field if 'property' is not available
                                                    if not prop_id:
                                                        prop_id = prop_item.get("id", "")

                                                    if prop_id and prop_value is not None:
                                                        # Special handling for DeviceINFO object
                                                        # Extract MAC, DBM, DBM_Level, IP from nested structure
                                                        if prop_id == "DeviceINFO" and isinstance(prop_value, dict):
                                                            # Extract MAC address
                                                            mac_value = prop_value.get("MAC")
                                                            if mac_value and "DeviceINFO_MAC" in device.properties:
                                                                device.properties["DeviceINFO_MAC"].value = mac_value

                                                            # Extract DBM (signal strength in dBm)
                                                            dbm_value = prop_value.get("DBM")
                                                            if dbm_value is not None and "DeviceINFO_DBM" in device.properties:
                                                                device.properties["DeviceINFO_DBM"].value = dbm_value

                                                            # Extract DBM_Level (signal strength level)
                                                            # Try to get DBM_Level directly, or convert from DBM
                                                            dbm_level_value = prop_value.get("DBM_Level")
                                                            if dbm_level_value is None and dbm_value is not None:
                                                                # Convert numeric DBM to level string if DBM_Level not provided
                                                                dbm_level_value = self._convert_dbm_to_level(dbm_value)
                                                            
                                                            if dbm_level_value is not None and "DeviceINFO_DBM_Level" in device.properties:
                                                                device.properties["DeviceINFO_DBM_Level"].value = dbm_level_value

                                                            # Extract IP address
                                                            ip_value = prop_value.get("IP")
                                                            if ip_value and "DeviceINFO_IP" in device.properties:
                                                                device.properties["DeviceINFO_IP"].value = ip_value
                                                        # Update regular property
                                                        elif prop_id in device.properties:
                                                            old_value = device.properties[prop_id].value
                                                            device.properties[prop_id].value = prop_value
                                                            if prop_id == "RSSI":
                                                                # Convert numeric DBM to level string
                                                                old_value = device.properties[prop_id].value
                                                                dbm_level = self._convert_dbm_to_level(prop_value)
                                                                device.properties[prop_id].value = dbm_level
                                                        else:
                                                            pass
                                                    else:
                                                        pass
                                    except Exception as err:
                                        _LOGGER.error(
                                            "Failed to parse deriveMetadata for %s: %s",
                                            device_id,
                                            err,
                                            exc_info=True,
                                        )
                    except Exception as err:
                        pass

                # 更新设备数据
                old_devices = self.data.devices.copy()
                self.data.devices = devices

                # 合并旧设备的状态（如果新设备没有该属性）
                for device_id, new_device in devices.items():
                    if device_id in old_devices:
                        old_device = old_devices[device_id]
                        # 保留旧设备的在线状态和其他动态属性
                        for prop_id, old_prop in old_device.properties.items():
                            if prop_id in new_device.properties:
                                # 保持最新值
                                if old_prop.value is not None:
                                    new_device.properties[prop_id].value = old_prop.value

                        # 复制在线状态
                        if not new_device.online and old_device.online:
                            new_device.online = old_device.online

            except ConfigEntryAuthFailed:
                raise
            except Exception as err:
                _LOGGER.error(
                    "Failed to fetch devices: %s\nException type: %s\nTraceback available in debug logs",
                    err,
                    type(err).__name__,
                    exc_info=True,  # Add full traceback for debugging
                )
                self.data.errors["devices"] = str(err)
                # 如果之前有设备数据，保持不变
                if not self.data.devices:
                    raise UpdateFailed(f"Failed to fetch devices: {err}") from err

            # 更新最后更新时间
            self.data.last_update = datetime.now()
            self.data.errors.clear()

            return self.data

        except ConfigEntryAuthFailed:
            _LOGGER.error("Authentication failed during data update")
            raise
        except Exception as err:
            _LOGGER.error("Unexpected error during data update: %s", err)
            raise UpdateFailed(f"Error fetching Heiman data: {err}") from err

    def get_device(self, device_id: str) -> HeimanDevice | None:
        """Get device by ID.
        
        Args:
            device_id: Device ID to retrieve
            
        Returns:
            HeimanDevice object or None if not found
        """
        return self.data.devices.get(device_id)

    def get_all_devices(self) -> list[HeimanDevice]:
        """Get all devices.
        
        Returns:
            List of all HeimanDevice objects
        """
        return list(self.data.devices.values())

    def get_devices_by_type(self, device_type: str) -> list[HeimanDevice]:
        """Get devices by type.
        
        Args:
            device_type: Device type to filter by
            
        Returns:
            List of matching HeimanDevice objects
        """
        return [
            device for device in self.data.devices.values()
            if device.device_type == device_type
        ]

    @staticmethod
    def _convert_dbm_to_level(dbm_value: int | float) -> str:
        """Convert numeric DBM value to signal strength level string.
        
        Args:
            dbm_value: Signal strength in dBm (negative number)
            
        Returns:
            Signal level string: "Strong", "Medium", "Weak", or "Very Weak"
        """
        # DBM values are typically negative numbers
        # Closer to 0 = stronger signal
        if dbm_value >= -50:
            return "Strong"
        elif dbm_value >= -65:
            return "Medium"
        elif dbm_value >= -75:
            return "Weak"
        else:
            return "Very Weak"

    async def async_init_mqtt_client(self) -> None:
        """Initialize MQTT client for real-time updates."""
        if self.mqtt_client:
            return

        try:
            # Get authentication data from config entry or API client
            access_token = None
            user_id = self.config_entry.data.get(CONF_USER_ID)

            # Try to get from config first
            access_token = self.config_entry.data.get("access_token")

            # Fallback: try to get from OAuth2 session if not in config
            if not access_token and self.oauth_session:
                try:
                    token_data = await self.oauth_session.async_ensure_token_valid()
                    if token_data:
                        access_token = token_data.get("access_token")
                    else:
                        _LOGGER.warning("async_ensure_token_valid() returned None")
                except Exception as err:
                    _LOGGER.warning("Failed to get access_token from session: %s", err)

            # Final fallback: get token from api_client
            if not access_token and hasattr(self.api_client, '_get_access_token'):
                try:
                    access_token = self.api_client._get_access_token()
                except Exception as err:
                    _LOGGER.warning("Failed to get access_token from api_client: %s", err)

            if not access_token:
                _LOGGER.warning("Cannot initialize MQTT: access_token not available from any source")
                return

            if not user_id:
                _LOGGER.warning("Cannot initialize MQTT: user_id not available")
                return
            
            # Get user display name (prefer nickName, fallback to email)
            user_display_name = None
            try:
                if self.data.user_info:
                    # Try to get nickName first
                    user_display_name = getattr(self.data.user_info, 'nick_name', None)
                    if not user_display_name:
                        # Fallback to email
                        user_display_name = getattr(self.data.user_info, 'email', None)
            except Exception as err:
                _LOGGER.warning("Failed to get user display name: %s", err)
            
            # Get cloud client reference for child device detection
            cloud_client = None
            try:
                if hasattr(self.api_client, '_cloud_client'):
                    cloud_client = self.api_client._cloud_client
            except Exception as err:
                _LOGGER.warning("Failed to get cloud_client reference: %s", err)
            
            # Get devices dictionary for child device detection
            devices_dict = dict(self.data.devices) if self.data.devices else {}

            # Create and connect MQTT client
            self.mqtt_client = HeimanMqttClient(
                hass=self.hass,
                access_token=access_token,
                user_id=user_id,
                user_display_name=user_display_name,
                cloud_client=cloud_client,
                devices=devices_dict,  # Pass devices dictionary
            )

            await self.mqtt_client.connect()

            # Register callback for device property updates
            self.mqtt_client.register_device_callback(self._on_device_property_update)

        except HeimanMQTTError as err:
            _LOGGER.error("Failed to initialize MQTT client: %s", err)
        except Exception as err:
            _LOGGER.error("Unexpected error initializing MQTT client: %s", err)

    def _on_device_property_update(self, device_id: str, properties: dict[str, Any]) -> None:
        """Handle device property update from MQTT.
        
        Args:
            device_id: Device ID that sent the update
            properties: Dictionary of property name to value
        """
        # Find device in coordinator data
        device = self.data.devices.get(device_id)
        if not device:
            return

        # Update device properties
        for prop_name, prop_value in properties.items():
            if prop_name in device.properties:
                device.properties[prop_name].value = prop_value
            else:
                # Add new property if it doesn't exist
                from heimanconnect import DeviceProperty
                device.properties[prop_name] = DeviceProperty(
                    identifier=prop_name,
                    name=prop_name,
                    value=prop_value,
                )

        # Schedule entity update if coordinator is set up
        # IMPORTANT: Must be called from the event loop thread for thread safety
        if hasattr(self, 'async_set_updated_data') and self.hass:
            # Use hass.add_job to schedule the update in the event loop
            # Pass the coroutine function and data as arguments
            self.hass.add_job(self.async_set_updated_data, self.data)

    async def async_read_device_properties(self, device_id: str) -> None:
        """Read properties from a specific device via MQTT.
        
        Args:
            device_id: Device ID to read properties from
        """
        if not self.mqtt_client:
            _LOGGER.warning("MQTT client not initialized, cannot read properties")
            return

        device = self.data.devices.get(device_id)
        if not device:
            _LOGGER.warning("Device %s not found in coordinator", device_id)
            return

        try:
            # Read all properties (empty list means read all)
            properties = await self.mqtt_client.async_read_properties(
                device_id=device_id,
                product_id=device.product_id,
                property_identifiers=None,  # Read all available properties
            )

            # Update device properties in coordinator data
            if properties:
                for prop_name, prop_value in properties.items():
                    if prop_name in device.properties:
                        device.properties[prop_name].value = prop_value
                    else:
                        # Add new property if it doesn't exist
                        from heimanconnect import DeviceProperty
                        device.properties[prop_name] = DeviceProperty(
                            identifier=prop_name,
                            name=prop_name,
                            value=prop_value,
                        )

                # Trigger entity update
                # IMPORTANT: Must be called from the event loop thread for thread safety
                if hasattr(self, 'async_set_updated_data') and self.hass:
                    # Use hass.add_job to schedule the update in the event loop
                    # Pass the coroutine function and data as arguments
                    self.hass.add_job(self.async_set_updated_data, self.data)
            else:
                _LOGGER.warning("No properties returned from device %s", device_id)

        except Exception as err:
            _LOGGER.error("Failed to read properties from device %s: %s", device_id, err)

    def get_online_devices(self) -> list[HeimanDevice]:
        """Get all online devices.
        
        Returns:
            List of online HeimanDevice objects
        """
        return [device for device in self.data.devices.values() if device.online]
    
    def get_device_property(self, device_id: str, property_name: str) -> Any | None:
        """Get device property value from cache.
        
        Args:
            device_id: Device ID
            property_name: Property name
            
        Returns:
            Property value if found, None otherwise
        """
        device = self.data.devices.get(device_id)
        if not device:
            return None
        
        prop = device.properties.get(property_name)
        if not prop:
            return None
        
        return prop.value
