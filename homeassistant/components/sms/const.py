"""Constants for sms Component."""

DOMAIN = "sms"
SMS_GATEWAY = "SMS_GATEWAY"
HASS_CONFIG = "sms_hass_config"
SMS_STATE_UNREAD = "UnRead"
SIGNAL_COORDINATOR = "signal_coordinator"
NETWORK_COORDINATOR = "network_coordinator"
GATEWAY = "gateway"
DEFAULT_SCAN_INTERVAL = 30
CONF_BAUD_SPEED = "baud_speed"
CONF_UNICODE = "unicode"
DEFAULT_BAUD_SPEED = "0"
DEFAULT_BAUD_SPEEDS = [
    {"value": DEFAULT_BAUD_SPEED, "label": "Auto"},
    {"value": "50", "label": "50"},
    {"value": "75", "label": "75"},
    {"value": "110", "label": "110"},
    {"value": "134", "label": "134"},
    {"value": "150", "label": "150"},
    {"value": "200", "label": "200"},
    {"value": "300", "label": "300"},
    {"value": "600", "label": "600"},
    {"value": "1200", "label": "1200"},
    {"value": "1800", "label": "1800"},
    {"value": "2400", "label": "2400"},
    {"value": "4800", "label": "4800"},
    {"value": "9600", "label": "9600"},
    {"value": "19200", "label": "19200"},
    {"value": "28800", "label": "28800"},
    {"value": "38400", "label": "38400"},
    {"value": "57600", "label": "57600"},
    {"value": "76800", "label": "76800"},
    {"value": "115200", "label": "115200"},
]
