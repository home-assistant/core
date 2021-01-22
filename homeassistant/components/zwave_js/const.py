"""Constants for the Z-Wave JS integration."""


DOMAIN = "zwave_js"
NAME = "Z-Wave JS"
PLATFORMS = ["binary_sensor", "climate", "cover", "light", "lock", "sensor", "switch"]

DATA_CLIENT = "client"
DATA_UNSUBSCRIBE = "unsubs"

EVENT_DEVICE_ADDED_TO_REGISTRY = f"{DOMAIN}_device_added_to_registry"
