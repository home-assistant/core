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
    api_version = info.get("API_VERSION")
    # Remove trailing slash from API version
    if api_version:
        api_version = api_version[:-1]
    return DeviceInfo(
        identifiers={(DOMAIN, info.get("SERIAL_NUMBER", "unknown"))},
        manufacturer=MANUFACTURER,
        model=info.get("MODEL") or None,
        model_id=info.get("MODEL_ID") or None,
        name=info.get("NAME") or None,
        serial_number=info.get("SERIAL_NUMBER") or None,
        sw_version=(
            f"{info.get('SW_VERSION', '')} (API {api_version})"
            if info.get("SW_VERSION") and api_version
            else None
        ),
        hw_version=(
            f"{info.get('FW_CODE', '')} (Firmware v{info.get('FW_VERSION', '')})"
            if info.get("FW_CODE") and info.get("FW_VERSION")
            else None
        ),
        connections={(CONNECTION_NETWORK_MAC, str(info["MAC"]))}
        if info.get("MAC")
        else set(),
        configuration_url=(
            f"http://{info['IP']}/index.html" if info.get("IP") else None
        ),
    )


# dynamic sensors
SENSOR_MAP: dict[str, tuple[SensorDeviceClass | None, EntityCategory | None, bool]] = {
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
