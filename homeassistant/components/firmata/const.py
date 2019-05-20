"""Constants for the Firmata component."""
import logging

LOGGER = logging.getLogger('.')
DOMAIN = "firmata"
PLATFORM_NAME = DOMAIN
SWITCH_DEFAULT_NAME = "DigitalOut"
CONF_NAME = "name"
CONF_PORT = "port"
CONF_HANDSHAKE = "handshake"
CONF_SERIAL_PORT = "serialport"

CONF_PINS = "pins"
CONF_PIN = "pin"
CONF_TYPE = "type"
CONF_DIGITAL_PULLUP = "pullup"
CONF_INITIAL_STATE = "initial"
CONF_NEGATE_STATE = "negate"
