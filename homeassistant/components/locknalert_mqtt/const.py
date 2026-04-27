"""Constants for LocknAlert integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "locknalert"
PLATFORMS: Final = [
    "binary_sensor",
    "sensor",
    "switch",
    "alarm_control_panel",
]

CONF_API_PORT: Final = "api_port"
CONF_BRIDGE_SERIAL: Final = "bridge_serial"
CONF_TLS_REQUIRED: Final = "tls_required"
CONF_LocknAlertMQTT: Final = "mqtt"
CONF_PREFIX: Final = "topic_prefix"
CONF_VERIFY_SSL: Final = "verify_ssl"
CONF_PAIRING_TOKEN: Final = "pairing_token"

DEFAULT_API_PORT: Final = 443
DEFAULT_LocknAlertMQTT_PORT: Final = 8883
DEFAULT_TOPIC_PREFIX: Final = "locknalert"

DATA_COORDINATOR: Final = "coordinator"
DATA_API: Final = "bridge_api"
DATA_LocknAlertMQTT: Final = "mqtt_client"

TOPIC_AVAILABILITY: Final = "availability"
TOPIC_STATUS: Final = "status"
TOPIC_ZONE: Final = "zone"
TOPIC_PARTITION: Final = "partition"
TOPIC_OUTPUT: Final = "output"
TOPIC_SENSOR: Final = "sensor"

ONLINE: Final = "online"
OFFLINE: Final = "offline"

COORDINATOR_DEBOUNCE: Final = timedelta(seconds=1)

ATTR_BRIDGE_SERIAL: Final = "bridge_serial"
ATTR_MODEL: Final = "model"
ATTR_FIRMWARE: Final = "firmware"
