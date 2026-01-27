"""Constants for the victron_mqtt integration."""

# Integration specific values (custom / builtin Home Assistant)
DOMAIN = "victron_gx_mqtt"
ENTITY_PREFIX = "victron"

# generic config values
CONF_INSTALLATION_ID = "installation_id"
CONF_MODEL = "model"
CONF_SERIAL = "serial"
CONF_ROOT_TOPIC_PREFIX = "root_topic_prefix"
CONF_UPDATE_FREQUENCY_SECONDS = "update_frequency"

DEVICE_MESSAGE = "device"
SENSOR_MESSAGE = "sensor"

DEFAULT_HOST = "venus.local."
DEFAULT_PORT = 1883
DEFAULT_UPDATE_FREQUENCY_SECONDS = 30

# Service names
SERVICE_PUBLISH = "publish"

# Service data attributes
ATTR_METRIC_ID = "metric_id"
ATTR_DEVICE_ID = "device_id"
ATTR_VALUE = "value"

# Not using GenericOnOff as some switches use different enums.
# It has to be with value "On" to be on and "Off" to be off.
SWITCH_ON = "On"
SWITCH_OFF = "Off"

# Entity IDs which needs special treatment
ENTITIES_CATEGORY_DIAGNOSTIC = ["system_heartbeat"]
ENTITIES_DISABLE_BY_DEFAULT = ["system_heartbeat"]
