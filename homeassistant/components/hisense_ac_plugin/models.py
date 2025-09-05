"""Data models for Hisense AC Plugin."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Protocol

from homeassistant.exceptions import HomeAssistantError

from .const import DeviceType, DEVICE_TYPES
from .devices import get_device_parser, BaseDeviceParser

_LOGGER = logging.getLogger(__name__)

class ApiClientProtocol(Protocol):
    """Protocol for API client."""
    
    @abstractmethod
    async def _api_request(
        self, 
        method: str, 
        path: str, 
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make API request."""
        ...

    @property
    @abstractmethod
    def oauth_session(self) -> Any:
        """Get OAuth session."""
        ...


@dataclass
class PushChannel:
    """Push channel information."""
    push_channel: str

    @classmethod
    def from_json(cls, json_data: dict) -> "PushChannel":
        """Create from JSON."""
        return cls(
            push_channel=json_data.get("pushChannel", "")
        )


@dataclass
class NotificationInfo:
    """Notification server information."""
    push_channels: List[PushChannel]
    push_server_ip: str
    push_server_port: str
    push_server_ssl_port: str
    hb_interval: int
    hb_fail_times: int
    has_msg_unread: int
    unread_msg_num: int

    @classmethod
    def from_json(cls, json_data: dict) -> "NotificationInfo":
        """Create from JSON."""
        return cls(
            push_channels=[PushChannel.from_json(c) for c in json_data.get("pushChannels", [])],
            push_server_ip=json_data.get("pushServerIp", ""),
            push_server_port=json_data.get("pushServerPort", ""),
            push_server_ssl_port=json_data.get("pushServerSslPort", ""),
            hb_interval=json_data.get("hbInterval", 30),
            hb_fail_times=json_data.get("hbFailTimes", 3),
            has_msg_unread=json_data.get("hasMsgUnread", 0),
            unread_msg_num=json_data.get("unreadMsgNum", 0)
        )


class DeviceInfo:
    """Device information class."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize device info."""
        if not isinstance(data, dict):
            _LOGGER.warning("DeviceInfo initialized with non-dict data: %s", data)
            data = {}
            
        # Basic device information
        self.wifi_id = data.get("wifiId")
        self.device_id = data.get("deviceId")
        self.puid = data.get("puid")
        self.name = data.get("deviceNickName")
        self.feature_code = data.get("deviceFeatureCode")
        self.feature_name = data.get("deviceFeatureName")
        self.type_code = data.get("deviceTypeCode")
        self.type_name = data.get("deviceTypeName")
        self.bind_time = data.get("bindTime")
        self.role = data.get("role")
        self.room_id = data.get("roomId")
        self.room_name = data.get("roomName")
        self._failed_data = []
        # Status information
        status_list = data.get("statusList", {})
        if isinstance(status_list, dict):
            self.status = status_list
        else:
            _LOGGER.warning("Invalid status data: %s", status_list)
            self.status = {}
            
        # Other information
        self.use_time = data.get("useTime")
        self.offline_state = data.get("offlineState")
        self.onOff = self.status.get("t_power")
        self.seq = data.get("seq")
        self.create_time = data.get("createTime")
        self._is_online = self.offline_state == 1
        self._is_onOff = self.onOff == 1 or self.onOff == "1"

        _LOGGER.debug(
            "Device %s (type: %s-%s) onOff: %s, _is_onOff: %s",
            self.feature_code,
            self.type_code, 
            self.feature_code, 
            self.onOff,
            self._is_onOff
        )

    @property
    def is_online(self) -> bool:
        """Return if device is online."""
        return self._is_online

    @property
    def failed_data(self) -> List[str]:
        """Property to access failed_data safely."""
        return self._failed_data
    @property
    def is_onOff(self) -> bool:
        """Return if device is online."""
        return self._is_onOff

    def get_device_type(self) -> DeviceType | None:
        """Get device type information."""
        if not self.type_code or not self.feature_code:
            _LOGGER.warning(
                "Cannot get device type: type_code=%s, feature_code=%s",
                self.type_code,
                self.feature_code
            )
            return None
            
        type_key = (self.type_code, self.feature_code)
        device_type = DeviceType(type_code=self.type_code, feature_code=self.feature_code, description=self.name)
        _LOGGER.debug("Created device type: %s", device_type)
        if not device_type:
            _LOGGER.warning(
                "Unsupported device type: %s-%s",
                self.type_code,
                self.feature_code
            )
        return device_type

    def is_supported(self) -> bool:
        """Check if this device type is supported."""
        supported_device_types = ["009", "008", "006"]
        return self.type_code in supported_device_types

    def is_devices(self) -> bool:
        """Check if this device type is supported."""
        #009 分体空调 008 窗机 007 除湿机 006 移动空调
        supported_device_types = ["009", "008", "007", "006", "016", "035"]
        return self.type_code in supported_device_types
    def is_water(self) -> bool:
        """Check if this device type is supported."""
        supported_device_types = ["016"]
        return self.type_code in supported_device_types
    def is_humidityr(self) -> bool:
        """Check if this device type is supported."""
        supported_device_types = ["007"]
        return self.type_code in supported_device_types
    def get_status_value(self, key: str, default: Any = None) -> Any:
        """Get value from status list."""
        return self.status.get(key, default)

    def has_attribute(self, key: str,parser: BaseDeviceParser) -> bool:
        """Check if device has a specific attribute."""
        # First check if the attribute exists in status
        # Check if the attribute is defined in the parser
        #先使用静态数据判断
        attributes = parser.attributes
        if attributes:
            _LOGGER.debug("Checking if device has status: %s", attributes)
            return key in attributes
        else:
            if key in self.status:
                return True

            # If not in status, check if we can get a parser for this device
            device_type = self.get_device_type()
            if not device_type:
                return False


            if not parser:
                return False


    def to_dict(self) -> dict[str, Any]:
        """Convert device info to dictionary."""
        # Return the data in the same format as the API response
        return {
            "wifiId": self.wifi_id,
            "deviceId": self.device_id,
            "puid": self.puid,
            "deviceNickName": self.name,
            "deviceFeatureCode": self.feature_code,
            "deviceFeatureName": self.feature_name,
            "deviceTypeCode": self.type_code,
            "deviceTypeName": self.type_name,
            "bindTime": self.bind_time,
            "role": self.role,
            "roomId": self.room_id,
            "roomName": self.room_name,
            "statusList": self.status,
            "useTime": self.use_time,
            "offlineState": self.offline_state,
            "seq": self.seq,
            "createTime": self.create_time
        }
        
    def debug_info(self) -> str:
        """Return detailed debug information about the device."""
        info = [
            f"Device: {self.name} ({self.device_id})",
            f"PUID: {self.puid}",
            f"Type: {self.type_code}-{self.feature_code} ({self.type_name} - {self.feature_name})",
            f"Online: {self.is_online} (offline_state: {self.offline_state})",
            f"Status: {self.status}",
            f"Supported: {self.is_supported()}"
        ]
        return "\n".join(info)

    @failed_data.setter
    def failed_data(self, value):
        self._failed_data = value


class HisenseApiError(HomeAssistantError):
    """Raised when API request fails."""
