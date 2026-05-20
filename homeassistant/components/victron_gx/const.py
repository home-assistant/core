"""Constants for the victron_gx integration."""

DOMAIN = "victron_gx"

CONF_INSTALLATION_ID = "installation_id"
# pylint: disable-next=home-assistant-duplicate-const
CONF_MODEL = "model"
CONF_SERIAL = "serial"
CONF_UPDATE_FREQUENCY = "update_frequency"

DEFAULT_UPDATE_FREQUENCY_SECONDS = 30

# Binary sensor enum ids must be "on" for on and "off" for off.
BINARY_SENSOR_ON_ID = "on"
BINARY_SENSOR_OFF_ID = "off"
