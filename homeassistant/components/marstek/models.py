"""Models for the Marstek integration."""

from collections.abc import Mapping
from dataclasses import dataclass

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    CONF_BLE_MAC,
    CONF_DEVICE_TYPE,
    CONF_VERSION,
    CONF_WIFI_MAC,
    CONF_WIFI_NAME,
    DOMAIN,
)

_RAW_DEVICE_TYPE = "device"
_RAW_VERSION = "ver"
_RAW_ID = "id"
_RAW_IP = "ip"

type MarstekDeviceVersion = int | str


@dataclass(frozen=True, slots=True)
class MarstekDeviceInfo:
    """Normalized Marstek device information."""

    id: object | None
    device_type: str
    version: MarstekDeviceVersion
    wifi_name: str
    ip: str
    wifi_mac: str
    ble_mac: str
    mac: str

    @classmethod
    def from_response(
        cls, device_info: Mapping[str, object], host: str | None = None
    ) -> MarstekDeviceInfo:
        """Normalize a Marstek discovery or device-info response."""
        wifi_mac = _string_value(device_info.get(CONF_WIFI_MAC))
        ble_mac = _string_value(device_info.get(CONF_BLE_MAC))

        return cls(
            id=device_info.get(_RAW_ID),
            device_type=_string_value(
                device_info.get(CONF_DEVICE_TYPE, device_info.get(_RAW_DEVICE_TYPE)),
                "Unknown",
            ),
            version=_version_value(
                device_info.get(CONF_VERSION, device_info.get(_RAW_VERSION))
            ),
            wifi_name=_string_value(device_info.get(CONF_WIFI_NAME)),
            ip=_string_value(
                device_info.get(CONF_HOST) or device_info.get(_RAW_IP) or host
            ),
            wifi_mac=wifi_mac,
            ble_mac=ble_mac,
            mac=_string_value(device_info.get(CONF_MAC)) or wifi_mac or ble_mac,
        )

    @property
    def stable_id(self) -> str:
        """Return the stable hardware identifier for the device."""
        return self.mac or self.wifi_mac or self.ble_mac

    @property
    def display_name(self) -> str:
        """Return the user-facing discovery display name."""
        wifi_name = self.wifi_name or "No WiFi"
        host = self.ip or "Unknown IP"
        return f"{self.device_type} v{self.version} ({wifi_name}) - {host}"

    @property
    def title(self) -> str:
        """Return the config entry title."""
        return f"Marstek {self.device_type} v{self.version} ({self.ip})"

    def as_config_entry_data(self) -> dict[str, object]:
        """Return config entry data for this device."""
        return {
            CONF_HOST: self.ip,
            CONF_MAC: self.mac,
            CONF_DEVICE_TYPE: self.device_type,
            CONF_VERSION: self.version,
            CONF_WIFI_NAME: self.wifi_name,
            CONF_WIFI_MAC: self.wifi_mac,
            CONF_BLE_MAC: self.ble_mac,
        }

    def as_device_info(self) -> DeviceInfo:
        """Return Home Assistant device registry metadata."""
        return {
            "identifiers": {(DOMAIN, self.stable_id)},
            "name": f"Marstek {self.device_type} v{self.version}",
            "manufacturer": "Marstek",
            "model": self.device_type,
            "sw_version": str(self.version),
        }


def _string_value(value: object, default: str = "") -> str:
    """Return value as a string, or a default for missing values."""
    if value is None:
        return default
    value = str(value)
    return value or default


def _version_value(value: object) -> MarstekDeviceVersion:
    """Return a display-safe firmware version value."""
    return value if isinstance(value, int | str) and value != "" else 0
