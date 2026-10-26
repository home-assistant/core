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

UNSUPPORTED_CONNECTIVITY_MODES = {"smartlink", "not_configured"}
CONNECTIVITY_ISSUE_PREFIX = "connectivity_issue_"

AIRTHINGS_CLOUD_DOCUMENTATION_URL = (
    "https://www.home-assistant.io/integrations/airthings"
)


def get_connectivity_mode(value: str | float | None) -> str | None:
    """Get connectivity mode."""
    if not isinstance(value, str):
        return None
    return CONNECTIVITY_MODE_MAP.get(value)
