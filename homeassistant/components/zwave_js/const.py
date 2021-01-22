"""Constants for the Z-Wave JS integration."""


DOMAIN = "zwave_js"
NAME = "Z-Wave JS"
PLATFORMS = ["binary_sensor", "climate", "light", "lock", "sensor", "switch"]

ATTR_NODE_ID = "node_id"

DATA_CLIENT = "client"
DATA_UNSUBSCRIBE = "unsubs"

EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"
