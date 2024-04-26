"""Constants for the virtual component."""

COMPONENT_DOMAIN = "virtual"
COMPONENT_SERVICES = "virtual-services"
COMPONENT_NETWORK = "virtual-network"
COMPONENT_MANUFACTURER = "dprg"
COMPONENT_MODEL = "virtual"

ATTR_AVAILABLE = "available"
ATTR_DEVICES = "devices"
ATTR_DEVICE_ID = "device_id"
ATTR_ENTITIES = "entities"
ATTR_FILE_NAME = "file_name"
ATTR_GROUP_NAME = "group_name"
ATTR_PARENT_ID = "parent_id"
ATTR_PERSISTENT = "persistent"
ATTR_UNIQUE_ID = "unique_id"
ATTR_VALUE = "value"
ATTR_VERSION = "version"

CONF_CLASS = "class"
CONF_INITIAL_AVAILABILITY = "initial_availability"
CONF_INITIAL_VALUE = "initial_value"
CONF_NAME = "name"
CONF_PERSISTENT = "persistent"
CONF_COORDINATED = "coordinated"
CONF_PUSH = "push"
CONF_SIMULATE_NETWORK = "simulate_network"


DEFAULT_AVAILABILITY = True
DEFAULT_PERSISTENT = True
DEFAULT_COORDINATED = False
DEFAULT_PUSH = False
DEFAULT_SIMULATE_NETWORK = False

IMPORTED_GROUP_NAME = "imported"
IMPORTED_YAML_FILE = "/workspaces/home-assistant-core/config/virtual.yaml"
META_JSON_FILE = "/workspaces/home-assistant-core/config/.storage/virtual.meta.json"
