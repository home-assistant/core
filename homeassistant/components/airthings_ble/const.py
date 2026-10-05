"""Constants for Airthings BLE."""

from airthings_ble import AirthingsConnectivityMode, AirthingsDeviceType

DOMAIN = "airthings_ble"
MFCT_ID = 820

DEVICE_MODEL = "device_model"

DEFAULT_SCAN_INTERVAL = 300
DEVICE_SPECIFIC_SCAN_INTERVAL = {AirthingsDeviceType.CORENTIUM_HOME_2.value: 1800}

MAX_RETRIES_AFTER_STARTUP = 5

CONNECTIVITY_MODE_MAP = {
    AirthingsConnectivityMode.BLE.value: "bluetooth",
    AirthingsConnectivityMode.SMARTLINK.value: "smartlink",
    AirthingsConnectivityMode.NOT_CONFIGURED.value: "not_configured",
}


def get_connectivity_mode(value: str | float | None) -> str | None:
    """Get connectivity mode."""
    if not isinstance(value, str):
        return None
    return CONNECTIVITY_MODE_MAP.get(value)


def connectivity_mode_issue_id(entry_id: str) -> str:
    """Return the connectivity mode issue id for a config entry."""
    return f"connectivity_mode_{entry_id}"
