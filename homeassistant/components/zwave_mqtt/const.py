"""Constants for the zwave_mqtt integration."""
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

DOMAIN = "zwave_mqtt"
DATA_UNSUBSCRIBE = "unsubscribe"
PLATFORMS = [SWITCH_DOMAIN]

# MQTT Topics
TOPIC_OPENZWAVE = "OpenZWave"

# Common Attributes
ATTR_INSTANCE_ID = "instance_id"
ATTR_SECURE = "secure"
ATTR_CONFIG_PARAMETER = "parameter"
ATTR_CONFIG_VALUE = "value"
ATTR_CONFIG_SIZE = "size"
ATTR_NODE_ID = "node_id"
ATTR_SCENE_ID = "scene_id"
ATTR_SCENE_LABEL = "scene_label"
ATTR_SCENE_VALUE_ID = "scene_value_id"
ATTR_SCENE_VALUE_LABEL = "scene_value_label"

# Service specific
SERVICE_ADD_NODE = "add_node"
SERVICE_REMOVE_NODE = "remove_node"
SERVICE_REMOVE_FAILED_NODE = "remove_failed_node"
SERVICE_REPLACE_FAILED_NODE = "replace_failed_node"
SERVICE_CANCEL_COMMAND = "cancel_command"
SERVICE_SET_CONFIG_PARAMETER = "set_config_parameter"

# Home Assistant Events
EVENT_SCENE_ACTIVATED = f"{DOMAIN}.scene_activated"

# Signals
SIGNAL_DELETE_ENTITY = f"{DOMAIN}_delete_entity"

# Discovery Information
DISC_COMMAND_CLASS = "command_class"
DISC_COMPONENT = "component"
DISC_GENERIC_DEVICE_CLASS = "generic_device_class"
DISC_GENRE = "genre"
DISC_INDEX = "index"
DISC_INSTANCE = "instance"
DISC_NODE_ID = "node_id"
DISC_OPTIONAL = "optional"
DISC_PRIMARY = "primary"
DISC_SCHEMAS = "schemas"
DISC_SPECIFIC_DEVICE_CLASS = "specific_device_class"
DISC_TYPE = "type"
DISC_VALUES = "values"
