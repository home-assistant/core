"""Constants for Pooldose integration.

All entity maps include an 'enabled_by_default' boolean as last tuple value.
This controls if the entity is enabled by default in the entity registry.
"""

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo

DOMAIN = "pooldose"

SCAN_INTERVAL = 600  # seconds
DEFAULT_HOST = "KOMMSPOT"  # Default host for PoolDose device, used in config flow

CONF_SERIALNUMBER = "serialnumber"

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
