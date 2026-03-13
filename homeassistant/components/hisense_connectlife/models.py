"""Data models for Hisense AC Plugin."""

from __future__ import annotations

import logging
from typing import Any

from connectlife_cloud.devices import BaseDeviceParser

from homeassistant.exceptions import HomeAssistantError

from .const import DeviceType

_LOGGER = logging.getLogger(__name__)


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
        self._failed_data: list[str] = []
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
        self._is_onOff = self.onOff in {1, "1"}

        _LOGGER.debug(
            "Device %s (type: %s-%s) onOff: %s, _is_onOff: %s",
            self.feature_code,
            self.type_code,
            self.feature_code,
            self.onOff,
            self._is_onOff,
        )

    @property
    def is_online(self) -> bool:
        """Return if device is online."""
        return self._is_online

    @property
    def failed_data(self) -> list[str]:
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
                self.feature_code,
            )
            return None

        device_type = DeviceType(
            type_code=self.type_code,
            feature_code=self.feature_code,
            description=self.name or "",
        )
        _LOGGER.debug("Created device type: %s", device_type)
        if not device_type:
            _LOGGER.warning(
                "Unsupported device type: %s-%s", self.type_code, self.feature_code
            )
        return device_type

    def is_supported(self) -> bool:
        """Check if this device type is supported."""
        supported_device_types = ["009", "008", "006"]
        return self.type_code in supported_device_types

    def is_devices(self) -> bool:
        """Check if this device type is supported."""
        # 009: Split AC, 008: Window AC, 007: Dehumidifier, 006: Portable AC
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

    def has_attribute(self, key: str, parser: BaseDeviceParser) -> bool:
        """Check if device has a specific attribute."""
        # First check if the attribute exists in status
        # Check if the attribute is defined in the parser
        # Use static data first to check
        attributes = parser.attributes
        if attributes:
            _LOGGER.debug("Checking if device has status: %s", attributes)
            return key in attributes
        if key in self.status:
            return True

        # If not in status, check if we can get a parser for this device
        device_type = self.get_device_type()
        if not device_type:
            return False

        if not parser:
            return False
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
            "createTime": self.create_time,
        }

    def debug_info(self) -> str:
        """Return detailed debug information about the device."""
        info = [
            f"Device: {self.name} ({self.device_id})",
            f"PUID: {self.puid}",
            f"Type: {self.type_code}-{self.feature_code} ({self.type_name} - {self.feature_name})",
            f"Online: {self.is_online} (offline_state: {self.offline_state})",
            f"Status: {self.status}",
            f"Supported: {self.is_supported()}",
        ]
        return "\n".join(info)

    def set_failed_data(self, value: list[str]) -> None:
        """Set failed data."""
        self._failed_data = value


class HisenseApiError(HomeAssistantError):
    """Raised when API request fails."""
