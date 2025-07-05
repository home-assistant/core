"""Constants for Pooldose integration.

All entity maps include an 'enabled_by_default' boolean as last tuple value.
This controls if the entity is enabled by default in the entity registry.
"""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

DOMAIN = "pooldose"

DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_SCAN_INTERVAL = 600  # seconds
DEFAULT_HOST = "KOMMSPOT"  # Default host for PoolDose device, used in config flow

CONF_SERIALNUMBER = "serialnumber"
CONF_INCLUDE_SENSITIVE_DATA = "include_sensitive_data"

MANUFACTURER = "SEKO"


def device_info(info: dict | None) -> DeviceInfo:
    """Return device info dict for Pooldose device."""
    info = info or {}
    return DeviceInfo(
        identifiers={(DOMAIN, info.get("SERIAL_NUMBER", "unknown"))},
        manufacturer=MANUFACTURER,
        model=info.get("MODEL"),
        model_id=info.get("MODEL_ID"),
        name=info.get("NAME"),
        serial_number=info.get("SERIAL_NUMBER"),
        sw_version=info.get("SW_VERSION"),
        hw_version=info.get("FW_CODE"),
        connections={(CONNECTION_NETWORK_MAC, str(info.get("MAC")))},
        configuration_url=f"http://{info.get('IP')}/index.html",
    )


STATIC_SENSOR_MAP: dict[
    str, tuple[SensorDeviceClass | None, EntityCategory | None, bool]
] = {
    # Static sensors
    "OWNERID": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "WIFI_SSID": (
        None,
        EntityCategory.DIAGNOSTIC,
        True,
    ),
    "WIFI_KEY": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "AP_SSID": (
        None,
        EntityCategory.DIAGNOSTIC,
        True,
    ),
    "AP_KEY": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "API_VERSION": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "FW_VERSION": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
}

# dynamic sensors
DYNAMIC_SENSOR_MAP: dict[
    str, tuple[SensorDeviceClass | None, EntityCategory | None, bool]
] = {
    "temperature": (
        SensorDeviceClass.TEMPERATURE,  # DeviceClass
        None,  # EntityCategory
        True,  # enabled_by_default
    ),
    "ph": (
        None,
        None,
        True,
    ),
    "orp": (
        None,
        None,
        True,
    ),
    "ph_type_dosing": (
        None,
        EntityCategory.DIAGNOSTIC,
        True,
    ),
    "peristaltic_ph_dosing": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "ofa_ph_value": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "orp_type_dosing": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "peristaltic_orp_dosing": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "ofa_orp_value": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "ph_calibration_type": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "ph_calibration_offset": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "ph_calibration_slope": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "orp_calibration_type": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "orp_calibration_offset": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "orp_calibration_slope": (
        None,
        EntityCategory.DIAGNOSTIC,
        False,
    ),
}

VALUE_CONVERSION_TABLE: dict[str, dict[str, str]] = {
    # pH Type Dosing
    "PDPR1H1HAW100_FW539187_w_1eklg44ro": {
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklg44ro_ALCALYNE|": "alcalyne",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklg44ro_ACID|": "acid",
    },
    # Peristaltic pH Dosing
    "PDPR1H1HAW100_FW539187_w_1eklj6euj": {
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklj6euj_OFF|": "off",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklj6euj_PROPORTIONAL|": "proportional",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklj6euj_ON_OFF|": "on_off",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklj6euj_TIMED|": "timed",
    },
    # ORP Type Dosing
    "PDPR1H1HAW100_FW539187_w_1eklgnolb": {
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklgnolb_LOW|": "low",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklgnolb_HIGH|": "high",
    },
    # Peristaltic ORP Dosing
    "PDPR1H1HAW100_FW539187_w_1eo1s18s8": {
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eo1s18s8_OFF|": "off",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eo1s18s8_PROPORTIONAL|": "proportional",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eo1s18s8_ON_OFF|": "on_off",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eo1s18s8_TIMED|": "timed",
    },
    "PDPR1H1HAW100_FW539187_w_1eklh8gb7": {
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8gb7_OFF|": "off",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8gb7_REFERENCE|": "reference",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8gb7_1_POINT|": "1_point",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8gb7_2_POINTS|": "2_points",
    },
    "PDPR1H1HAW100_FW539187_w_1eklh8i5t": {
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8i5t_OFF|": "off",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8i5t_REFERENCE|": "reference",
        "|PDPR1H1HAW100_FW539187_LABEL_w_1eklh8i5t_1_POINT|": "1_point",
    },
}
