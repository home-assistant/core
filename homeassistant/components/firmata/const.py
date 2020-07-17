"""Constants for the Firmata component."""
import logging

LOGGER = logging.getLogger(__package__)

CONF_ARDUINO_INSTANCE_ID = "arduino_instance_id"
CONF_ARDUINO_WAIT = "arduino_wait"
CONF_BINARY_SENSORS = "binary_sensors"
CONF_INITIAL_STATE = "initial"
CONF_NAME = "name"
CONF_NEGATE_STATE = "negate"
CONF_PIN = "pin"
CONF_PINS = "pins"
CONF_PIN_MODE = "pin_mode"
PIN_MODE_OUTPUT = "OUTPUT"
PIN_MODE_INPUT = "INPUT"
PIN_MODE_PULLUP = "PULLUP"
CONF_SAMPLING_INTERVAL = "sampling_interval"
CONF_SERIAL_BAUD_RATE = "serial_baud_rate"
CONF_SERIAL_PORT = "serial_port"
CONF_SLEEP_TUNE = "sleep_tune"
CONF_SWITCHES = "switches"
DOMAIN = "firmata"
FIRMATA_MANUFACTURER = "Firmata"
