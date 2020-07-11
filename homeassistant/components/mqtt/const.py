"""Constants used by multiple MQTT modules."""
ATTR_DISCOVERY_HASH = "discovery_hash"
ATTR_DISCOVERY_PAYLOAD = "discovery_payload"
ATTR_DISCOVERY_TOPIC = "discovery_topic"
ATTR_PAYLOAD = "payload"
ATTR_QOS = "qos"
ATTR_RETAIN = "retain"
ATTR_TOPIC = "topic"

CONF_BROKER = "broker"
CONF_BIRTH_MESSAGE = "birth_message"
CONF_DISCOVERY = "discovery"
CONF_QOS = ATTR_QOS
CONF_RETAIN = ATTR_RETAIN
CONF_STATE_TOPIC = "state_topic"
CONF_WILL_MESSAGE = "will_message"

DEFAULT_DISCOVERY = False
DEFAULT_QOS = 0
DEFAULT_RETAIN = False

MQTT_CONNECTED = "mqtt_connected"
MQTT_DISCONNECTED = "mqtt_disconnected"

PROTOCOL_311 = "3.1.1"
