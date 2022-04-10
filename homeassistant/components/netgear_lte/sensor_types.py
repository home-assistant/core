"""Define possible sensor types."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    DATA_MEBIBYTES,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)

SENSOR_SMS = "sms"
SENSOR_SMS_TOTAL = "sms_total"
SENSOR_USAGE = "usage"

SENSOR_UNITS = {
    SENSOR_SMS: "unread",
    SENSOR_SMS_TOTAL: "messages",
    SENSOR_USAGE: DATA_MEBIBYTES,
    "radio_quality": PERCENTAGE,
    "rx_level": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    "tx_level": SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    "upstream": None,
    "connection_text": None,
    "connection_type": None,
    "current_ps_service_type": None,
    "register_network_display": None,
    "current_band": None,
    "cell_id": None,
}

BINARY_SENSOR_MOBILE_CONNECTED = "mobile_connected"

BINARY_SENSOR_CLASSES = {
    "roaming": None,
    "wire_connected": BinarySensorDeviceClass.CONNECTIVITY,
    BINARY_SENSOR_MOBILE_CONNECTED: BinarySensorDeviceClass.CONNECTIVITY,
}

ALL_SENSORS = list(SENSOR_UNITS)
DEFAULT_SENSORS = [SENSOR_USAGE]

ALL_BINARY_SENSORS = list(BINARY_SENSOR_CLASSES)
DEFAULT_BINARY_SENSORS = [BINARY_SENSOR_MOBILE_CONNECTED]
