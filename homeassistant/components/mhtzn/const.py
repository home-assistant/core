"""Constants used by multiple MQTT modules."""

DOMAIN = "mhtzn"

CONF_BROKER = "broker"

CONF_LIGHT_DEVICE_TYPE = "light_device_type"

FLAG_IS_INITIALIZED = "flag_is_initialized"

CACHE_ENTITY_STATE_UPDATE_KEY_DICT = "mhtzn_entity_state_update_dict"

EVENT_ENTITY_STATE_UPDATE = "mhtzn_entity_state_update_{}"

EVENT_ENTITY_REGISTER = "mhtzn_entity_register_{}"

MQTT_CLIENT_INSTANCE = "mqtt_client_instance"

MQTT_TOPIC_PREFIX = DOMAIN

PLATFORMS: list[str] = [
    "cover",
    "light",
    "scene"
]
