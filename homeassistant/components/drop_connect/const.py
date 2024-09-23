"""Constants for the drop_connect integration."""

# Keys for values used in the config_entry data dictionary
CONF_COMMAND_TOPIC = "drop_command_topic"
CONF_DATA_TOPIC = "drop_data_topic"
CONF_DEVICE_DESC = "device_desc"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_TYPE = "device_type"
CONF_HUB_ID = "drop_hub_id"
CONF_DEVICE_NAME = "name"
CONF_DEVICE_OWNER_ID = "drop_device_owner_id"

# Values for DROP device types
DEV_ALERT = "alrt"
DEV_FILTER = "filt"
DEV_HUB = "hub"
DEV_LEAK_DETECTOR = "leak"
DEV_PROTECTION_VALVE = "pv"
DEV_PUMP_CONTROLLER = "pc"
DEV_RO_FILTER = "ro"
DEV_SALT_SENSOR = "salt"
DEV_SOFTENER = "soft"

DISCOVERY_TOPIC = "drop_connect/discovery/#"

DOMAIN = "drop_connect"
