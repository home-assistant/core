"""Constants for Pooldose integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo

DOMAIN = "pooldose"
CONF_SERIALNUMBER = "serialnumber"

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_SCAN_INTERVAL = 600  # seconds

SOFTWARE_VERSION = "2.10"  # Extract from Pooldose web interface under admin:info

MANUFACTURER = "SEKO"
MODEL = "PoolDose Dual pH/ORP Wifi"
DEVICE_NAME = "PoolDose"


def device_info(info: dict | None) -> DeviceInfo:
    """Return device info dict for Pooldose device."""
    info = info or {}
    return DeviceInfo(
        identifiers={(DOMAIN, info.get("SERIAL_NUMBER", "unknown"))},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=info.get("SYSTEMNAME") or DEVICE_NAME,
        serial_number=info.get("SERIAL_NUMBER"),
        sw_version=info.get("SOFTWAREVERSION_GATEWAY"),
        hw_version=info.get("FIRMWARECODE_DEVICE"),
    )


SENSOR_MAP: dict[
    str, tuple[str, str | None, str | None, str, EntityCategory | None]
] = {
    "pool_temp_actual": (
        "pool_temp_actual",
        "°C",
        SensorDeviceClass.TEMPERATURE,
        "PDPR1H1HAW100_FW539187_w_1eommf39k",
        None,
    ),
    "pool_ph_actual": (
        "pool_ph_actual",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187_w_1ekeigkin",
        None,
    ),
    "pool_orp_actual": (
        "pool_orp_actual",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklenb23",
        None,
    ),
    "pool_systemname": (
        "pool_systemname",
        None,
        None,
        "SYSTEMNAME",
        EntityCategory.DIAGNOSTIC,
    ),
    "pool_ownerid": (
        "pool_ownerid",
        None,
        None,
        "OWNERID",
        EntityCategory.DIAGNOSTIC,
    ),
    "pool_ssid": (
        "pool_ssid",
        None,
        None,
        "SSID",
        EntityCategory.DIAGNOSTIC,
    ),
    "pool_ip": (
        "pool_ip",
        None,
        None,
        "IP",
        EntityCategory.DIAGNOSTIC,
    ),
    "pool_mac": (
        "pool_mac",
        None,
        None,
        "MAC",
        EntityCategory.DIAGNOSTIC,
    ),
    "pool_ap_ssid": (
        "pool_ap_ssid",
        None,
        None,
        "AP_SSID",
        EntityCategory.DIAGNOSTIC,
    ),
    "pool_ap_key": (
        "pool_ap_key",
        None,
        None,
        "AP_KEY",
        EntityCategory.DIAGNOSTIC,
    ),
}

# Static keys for static sensors (device info)
STATIC_SENSOR_KEYS: set[str] = {
    "SSID",
    "MAC",
    "IP",
    "SYSTEMNAME",
    "GROUPNAME",
    "OWNERID",
    "AP_SSID",
    "AP_KEY",
}

SWITCHES: dict[str, tuple[str, str, str, str, EntityCategory | None, str | None]] = {
    "stop_pool_dosing": (
        "stop_pool_dosing",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
        "F",
        "O",
        None,
        None,  # device_class
    ),
}

BINARY_SENSOR_MAP: dict[str, tuple[str, str, EntityCategory | None, str | None]] = {
    "stop_pool_dosing_state": (
        "stop_pool_dosing_state",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
        None,
        BinarySensorDeviceClass.PROBLEM,
    ),
    "pool_circulation_state": (
        "pool_circulation_state",
        "PDPR1H1HAW100_FW539187_w_1ekga097n",
        EntityCategory.DIAGNOSTIC,
        BinarySensorDeviceClass.POWER,
    ),
}

NUMBER_MAP: dict[
    str, tuple[str, str, dict[str, float | str], EntityCategory | None, str | None]
] = {
    "pool_ph_target": (
        "pool_ph_target",
        "PDPR1H1HAW100_FW539187_w_1ekeiqfat",
        {"min": 6.0, "max": 8.0, "unit": "pH", "resolution": 0.1},
        EntityCategory.CONFIG,
        None,  # device_class
    ),
    "pool_orp_target": (
        "pool_orp_target",
        "PDPR1H1HAW100_FW539187_w_1eklgnjk2",
        {"min": 400, "max": 850, "unit": "mV", "resolution": 50},
        EntityCategory.CONFIG,
        None,  # device_class
    ),
}

# for testing only:
DEFAULT_HOST = "192.168.178.137"
DEFAULT_SERIAL_NUMBER = "01220000095B"
