"""Constants for the MotionBlinds BLE integration."""

from enum import StrEnum

ATTR_CALIBRATION = "calibration"
ATTR_CONNECTION_TYPE = "connection_type"
ATTR_SPEED = "speed"
ATTR_BATTERY = "battery"
ATTR_CONNECT = "connect"
ATTR_DISCONNECT = "disconnect"
ATTR_FAVORITE = "favorite"
ATTR_SIGNAL_STRENGTH = "signal_strength"

CONF_LOCAL_NAME = "local_name"
CONF_MAC_CODE = "mac_code"
CONF_BLIND_TYPE = "blind_type"

DOMAIN = "motionblinds_ble"

ENTITY_NAME = "MotionBlind {mac_code}"

ERROR_COULD_NOT_FIND_MOTOR = "could_not_find_motor"
ERROR_INVALID_MAC_CODE = "invalid_mac_code"
ERROR_NO_BLUETOOTH_ADAPTER = "no_bluetooth_adapter"
ERROR_NO_DEVICES_FOUND = "no_devices_found"

EXCEPTION_NOT_CALIBRATED = (
    "{device_name} needs to be calibrated using the MotionBlinds BLE app before usage."
)

ICON_CALIBRATION = "mdi:tune"
ICON_SPEED = "mdi:run-fast"
ICON_CONNECT = "mdi:bluetooth"
ICON_DISCONNECT = "mdi:bluetooth-off"
ICON_FAVORITE = "mdi:star"
ICON_CONNECTION_TYPE = "mdi:bluetooth-connect"
ICON_VERTICAL_BLIND = "mdi:blinds-vertical-closed"

MANUFACTURER = "MotionBlinds"

SETTING_MAX_MOTOR_FEEDBACK_TIME = 2  # Seconds


class MotionCalibrationType(StrEnum):
    """Enum for the blind calibration type."""

    CALIBRATED = "calibrated"
    UNCALIBRATED = "uncalibrated"
    CALIBRATING = "calibrating"


class MotionBlindType(StrEnum):
    """Enum for the blind type."""

    ROLLER = "Roller blind"
    HONEYCOMB = "Honeycomb blind"
    ROMAN = "Roman blind"
    VENETIAN = "Venetian blind"
    VENETIAN_TILT_ONLY = "Venetian blind (tilt-only)"
    DOUBLE_ROLLER = "Double Roller blind"
    CURTAIN = "Curtain blind"
    VERTICAL = "Vertical blind"
