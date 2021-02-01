"""Constants for the Z-Wave JS integration."""
CONF_INTEGRATION_CREATED_ADDON = "integration_created_addon"
CONF_USE_ADDON = "use_addon"
DOMAIN = "zwave_js"
PLATFORMS = [
    "binary_sensor",
    "climate",
    "cover",
    "fan",
    "light",
    "lock",
    "sensor",
    "switch",
]

DATA_CLIENT = "client"
DATA_UNSUBSCRIBE = "unsubs"

EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"

# constants for events
ZWAVE_JS_EVENT = f"{DOMAIN}_event"
ATTR_NODE_ID = "node_id"
ATTR_HOME_ID = "home_id"
ATTR_ENDPOINT = "endpoint"
ATTR_LABEL = "label"
ATTR_VALUE = "value"
ATTR_COMMAND_CLASS = "command_class"
ATTR_COMMAND_CLASS_NAME = "command_class_name"
ATTR_TYPE = "type"
ATTR_DOMAIN = "domain"
ATTR_DEVICE_ID = "device_id"
ATTR_PROPERTY_NAME = "property_name"
ATTR_PROPERTY_KEY_NAME = "property_key_name"
