"""Constants for the victron_gx integration."""

DOMAIN = "victron_gx"

CONF_INSTALLATION_ID = "installation_id"
CONF_STATE_WRITE_DEBOUNCE_INTERVAL = "state_write_debounce_interval"
CONF_SERIAL = "serial"

DEFAULT_STATE_WRITE_DEBOUNCE_INTERVAL = 30.0

# Binary sensor enum ids must be "on" for on and "off" for off.
BINARY_SENSOR_ON_ID = "on"
BINARY_SENSOR_OFF_ID = "off"
