"""Define possible sensor types."""

from homeassistant.components.binary_sensor import DEVICE_CLASS_CONNECTIVITY

SENSOR_SMS = "sms"
SENSOR_SMS_TOTAL = "sms_total"
SENSOR_USAGE = "usage"

SENSOR_UNITS = {
    SENSOR_SMS: "unread",
    SENSOR_SMS_TOTAL: "messages",
    SENSOR_USAGE: "MiB",
    "wwanadv.radioquality": "%",
    "wwanadv.rxlevel": "dBm",
    "wwanadv.txlevel": "dBm",
}

BINARY_SENSOR_CLASSES = {
    "roaming": None,
    "wire_connected": DEVICE_CLASS_CONNECTIVITY,
    "mobile_connected": DEVICE_CLASS_CONNECTIVITY,
}

ALL_SENSORS = [x for x in SENSOR_UNITS if "." not in x]

ALL_BINARY_SENSORS = list(BINARY_SENSOR_CLASSES)
