"""Constants for the Qube Heat Pump integration."""

DOMAIN = "qube_heatpump"
PLATFORMS = ["sensor"]

TARIFF_OPTIONS = ("CV", "SWW")

CONF_HOST = "host"
CONF_PORT = "port"
CONF_UNIT_ID = "unit_id"
CONF_LABEL = "label"
CONF_SHOW_LABEL_IN_NAME = "show_label_in_name"
CONF_FRIENDLY_NAME_LANGUAGE = "friendly_name_language"
DEFAULT_FRIENDLY_NAME_LANGUAGE = "nl"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 10

# Name of the bundled Modbus specification file
CONF_FILE_NAME = "modbus.yaml"
