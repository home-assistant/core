"""Constants for the Qingping integration."""

from typing import Final

DOMAIN = "qingping"

CONF_CONNECTION_TYPE: Final = "connection_type"
CONNECTION_BLUETOOTH: Final = "bluetooth"
CONNECTION_MQTT: Final = "mqtt"

MQTT_TOPIC_PREFIX: Final = "qingping"

# Device models supported via MQTT (TLV protocol)
MODELS: Final[dict[str, str]] = {
    "cgr1w": "Qingping Indoor Environment Monitor",
}

# The device publishes realtime data every few minutes; without a message for
# this long it is considered offline
OFFLINE_TIMEOUT: Final = 900
OFFLINE_CHECK_INTERVAL: Final = 60
