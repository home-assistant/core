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
CONF_ADDRESS = "address"
CONF_MAC_CODE = "mac_code"
CONF_BLIND_TYPE = "blind_type"

DOMAIN = "motionblinds_ble"

ENTITY_NAME = "MotionBlind {mac_code}"

ERROR_ALREADY_CONFIGURED = "already_configured"
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

MANUFACTURER = "MotionBlinds - Coulisse"

SETTING_MAX_MOTOR_FEEDBACK_TIME = 2  # Seconds


class MotionCalibrationType(StrEnum):
    """Enum for the blind calibration type."""

    CALIBRATED = "calibrated"
    UNCALIBRATED = "uncalibrated"
    CALIBRATING = "calibrating"


class MotionBlindType(StrEnum):
    """Enum for the blind type."""

    ROLLER = "roller"
    HONEYCOMB = "honeycomb"
    ROMAN = "roman"
    VENETIAN = "venetian"
    VENETIAN_TILT_ONLY = "venetian_tilt_only"
    DOUBLE_ROLLER = "double_roller"
    CURTAIN = "curtain"
    VERTICAL = "vertical"
