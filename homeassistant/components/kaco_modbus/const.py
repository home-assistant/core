"""Constants for the KACO Modbus integration."""

DOMAIN = "kaco_modbus"

CONF_UNIT_ID = "unit_id"

DEFAULT_PORT = 502
# Ignored by TCP-native inverters, but not by one behind an RS485 gateway.
DEFAULT_UNIT_ID = 1
