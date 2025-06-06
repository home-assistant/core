"""Constants for Pooldose integration.

All entity maps include an 'enabled_by_default' boolean as last tuple value.
This controls if the entity is enabled by default in the entity registry.
"""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory, UnitOfVolume
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

DOMAIN = "pooldose"
DEFAULT_TIMEOUT = 30  # seconds
DEFAULT_SCAN_INTERVAL = 600  # seconds

CONF_SERIALNUMBER = "serialnumber"
SOFTWARE_VERSION = "2.10"  # Extract from Pooldose web interface under admin:info

APIVERSION = "v1"  # API version supported by the integration

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
        hw_version=info.get("FIRMWARERELEASE_DEVICE"),
        connections={
            (CONNECTION_NETWORK_MAC, str(info.get("MAC"))),
        },
        configuration_url=f"http://{info.get('IP')}/index.html",
        suggested_area=info.get("Pool"),
    )


SENSOR_MAP: dict[
    str, tuple[str, str | None, str | None, str, EntityCategory | None, bool]
] = {
    "pool_temp_actual": (
        "pool_temp_actual",
        "°C",
        SensorDeviceClass.TEMPERATURE,
        "PDPR1H1HAW100_FW539187_w_1eommf39k",
        None,
        True,
    ),
    "pool_ph_actual": (
        "pool_ph_actual",
        "pH",
        None,
        "PDPR1H1HAW100_FW539187_w_1ekeigkin",
        None,
        True,
    ),
    "pool_orp_actual": (
        "pool_orp_actual",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklenb23",
        None,
        True,
    ),
    "pool_ph_type_dosing": (
        "pool_ph_type_dosing",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1eklg44ro",
        EntityCategory.DIAGNOSTIC,
        True,
    ),
    "pool_peristaltic_ph_dosing": (
        "pool_peristaltic_ph_dosing",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1eklj6euj",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_ofa_ph_value": (
        "pool_ofa_ph_value",
        "min",
        None,
        "PDPR1H1HAW100_FW539187_w_1eo1ttmft",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_orp_type_dosing": (
        "pool_orp_type_dosing",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1eklgnolb",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_peristaltic_orp_dosing": (
        "pool_peristaltic_orp_dosing",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1eo1s18s8",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_ofa_orp_value": (
        "pool_ofa_orp_value",
        "min",
        None,
        "PDPR1H1HAW100_FW539187_w_1eo1tui1d",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # pH Calibration Type
    "pool_ph_calibration_type": (
        "pool_ph_calibration_type",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1eklh8gb7",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # pH Calibration Offset
    "pool_ph_calibration_offset": (
        "pool_ph_calibration_offset",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklhs3b4",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # pH Calibration Slope
    "pool_ph_calibration_slope": (
        "pool_ph_calibration_slope",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklhs65u",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # ORP Calibration Type
    "pool_orp_calibration_type": (
        "pool_orp_calibration_type",
        None,
        None,
        "PDPR1H1HAW100_FW539187_w_1eklh8i5t",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # ORP Calibration Offset
    "pool_orp_calibration_offset": (
        "pool_orp_calibration_offset",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklhs8r3",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # ORP Calibration Slope
    "pool_orp_calibration_slope": (
        "pool_orp_calibration_slope",
        "mV",
        None,
        "PDPR1H1HAW100_FW539187_w_1eklhsase",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    # Static sensors
    "pool_ownerid": (
        "pool_ownerid",
        None,
        None,
        "OWNERID",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_ssid": (
        "pool_ssid",
        None,
        None,
        "SSID",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_ap_ssid": (
        "pool_ap_ssid",
        None,
        None,
        "AP_SSID",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_ap_key": (
        "pool_ap_key",
        None,
        None,
        "AP_KEY",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
    "pool_api_version": (
        "pool_api_version",
        None,
        None,
        "APIVERSION_GATEWAY",
        EntityCategory.DIAGNOSTIC,
        False,
    ),
}

# Static keys for static sensors (device info)
STATIC_SENSOR_KEYS: set[str] = {
    "SSID",
    "GROUPNAME",
    "OWNERID",
    "AP_SSID",
    "AP_KEY",
    "APIVERSION_GATEWAY",
}

SWITCHES: dict[
    str, tuple[str, str, str, str, EntityCategory | None, str | None, bool]
] = {
    "stop_pool_dosing": (
        "stop_pool_dosing",
        "PDPR1H1HAW100_FW539187_w_1emtltkel",
        "F",
        "O",
        None,
        None,  # device_class
        True,
    ),
    "circulation_detection": (
        "circulation_detection",
        "PDPR1H1HAW100_FW539187_w_1eklft47q",
        "F",
        "O",
        EntityCategory.CONFIG,
        None,  # device_class
        True,
    ),
    "frequency_input": (
        "frequency_input",
        "PDPR1H1HAW100_FW539187_w_1eklft5qt",
        "F",
        "O",
        EntityCategory.CONFIG,
        None,  # device_class
        False,
    ),
}

BINARY_SENSOR_MAP: dict[
    str, tuple[str, str, EntityCategory | None, str | None, bool]
] = {
    "pool_circulation_state": (
        "pool_circulation_state",
        "PDPR1H1HAW100_FW539187_w_1ekga097n",
        None,
        BinarySensorDeviceClass.RUNNING,
        True,
    ),
    "pool_ph_level_ok": (
        "pool_ph_level_ok",
        "PDPR1H1HAW100_FW539187_w_1eklf77pm",
        None,
        None,
        True,
    ),
    "pool_orp_level_ok": (
        "pool_orp_level_ok",
        "PDPR1H1HAW100_FW539187_w_1eo04bcr2",
        None,
        None,
        True,
    ),
    "pool_flow_rate_ok": (
        "pool_flow_rate_ok",
        "PDPR1H1HAW100_FW539187_w_1eo04nc5n",
        None,
        None,
        False,
    ),
    "pool_alarm_relay": (
        "pool_alarm_relay",
        "PDPR1H1HAW100_FW539187_w_1eklffdl0",
        EntityCategory.DIAGNOSTIC,
        None,
        False,
    ),
    "pool_relay_aux1_ph": (
        "pool_relay_aux1_ph",
        "PDPR1H1HAW100_FW539187_w_1eoi2rv4h",
        EntityCategory.DIAGNOSTIC,
        None,
        True,
    ),
    "pool_relay_aux2_orpcl": (
        "pool_relay_aux2_orpcl",
        "PDPR1H1HAW100_FW539187_w_1eoi2s16b",
        EntityCategory.DIAGNOSTIC,
        None,
        True,
    ),
}

NUMBER_MAP: dict[
    str,
    tuple[str, str, dict[str, float | str], EntityCategory | None, str | None, bool],
] = {
    "pool_ph_target": (
        "pool_ph_target",
        "PDPR1H1HAW100_FW539187_w_1ekeiqfat",
        {"min": 6.0, "max": 8.0, "unit": "pH", "resolution": 0.1},
        EntityCategory.CONFIG,
        None,  # device_class
        True,
    ),
    "pool_orp_target": (
        "pool_orp_target",
        "PDPR1H1HAW100_FW539187_w_1eklgnjk2",
        {"min": 400, "max": 850, "unit": "mV", "resolution": 50},
        EntityCategory.CONFIG,
        None,  # device_class
        True,
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

SELECT_MAP: dict[
    str,
    tuple[
        str,  # entity_id
        str,  # key
        list[tuple[int, str]],  # options (value, translation_key)
        EntityCategory | None,
        bool,  # enabled_by_default
    ],
] = {
    "pool_water_meter_unit": (
        "pool_water_meter_unit",
        "PDPR1H1HAW100_FW539187_w_1eklinki6",
        [
            (0, "PDPR1H1HAW100_FW539187_COMBO_w_1eklinki6_M_"),
            (1, "PDPR1H1HAW100_FW539187_COMBO_w_1eklinki6_LITER"),
        ],
        EntityCategory.CONFIG,
        False,
    ),
}

# Conversion table for select options to user-friendly labels
SELECT_OPTION_CONVERSION: dict[str, dict[str, str]] = {
    "pool_water_meter_unit": {
        "PDPR1H1HAW100_FW539187_COMBO_w_1eklinki6_M_": UnitOfVolume.CUBIC_METERS,
        "PDPR1H1HAW100_FW539187_COMBO_w_1eklinki6_LITER": UnitOfVolume.LITERS,
    }
}

# for testing only:
DEFAULT_HOST = "192.168.178.137"
